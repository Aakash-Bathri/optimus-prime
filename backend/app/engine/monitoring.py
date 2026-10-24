"""Auditable projections over historical billing; no infrastructure mutations."""
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from math import sqrt
from statistics import fmean
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, model_validator

from app.database import connect
from app.engine.expenses import billing_range


class Scenario(BaseModel):
    days: int = Field(default=30, ge=30, le=90)
    shutdown: bool = True
    shutdown_environment: str = Field(default="development", pattern="^(development|staging|production)$")
    stop_hour: int = Field(default=20, ge=0, le=23)
    start_hour: int = Field(default=8, ge=0, le=23)
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)
    timezone: str = "Asia/Kolkata"
    demand_growth_pct: float = Field(default=0, ge=-50, le=100)
    budget: float | None = Field(default=None, gt=0, le=1e12)
    cost_increase_pct: float = Field(default=5, ge=0, le=1000)
    capacity_pct: float = Field(default=80, ge=1, le=100)
    watts_per_vcpu: float = Field(default=12, gt=0, le=1000)
    pue: float = Field(default=1.4, ge=1, le=3)
    carbon_kg_per_kwh: float = Field(default=0.7, ge=0, le=2)

    @model_validator(mode="after")
    def validate_schedule(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid IANA timezone")
        if any(day < 0 or day > 6 for day in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("Weekdays must be unique integers from 0 (Monday) to 6")
        if self.shutdown and self.stop_hour == self.start_hour:
            raise ValueError("Shutdown and restart hours must differ")
        return self


def project(app, scope, scenario: Scenario):
    resources = app.resources(scope)
    history = app.billing_history({r.id for r in resources})
    _, cutoff = billing_range(app.database_path)
    # Compare daily run rates to avoid treating month length as growth.
    rates = [float(p["amount"]) / monthrange(int(p["month"][:4]), int(p["month"][5:]))[1] for p in history]
    n = len(rates)
    slope = ((sum((i - (n - 1) / 2) * (y - fmean(rates)) for i, y in enumerate(rates)) /
              sum((i - (n - 1) / 2) ** 2 for i in range(n))) if n > 1 else 0)
    residual = sqrt(fmean((y - (fmean(rates) + slope * (i - (n - 1) / 2))) ** 2 for i, y in enumerate(rates))) if n else 0
    latest = rates[-1] if rates else 0
    plans = {p.id: p for p in app.plans()}
    selected = [r for r in resources if scenario.shutdown and r.type == "vm" and r.status == "running" and r.environment == scenario.shutdown_environment]
    tz = ZoneInfo(scenario.timezone)
    forecast_start = max(cutoff + timedelta(days=1), datetime.now(tz).date() + timedelta(days=1))
    points = []
    total_off = 0
    for offset in range(1, scenario.days + 1):
        day = forecast_start + timedelta(days=offset - 1)
        evidence_age = (day - cutoff).days
        off = 0
        for hour in range(24):
            local = datetime.combine(day, time(hour), tzinfo=ZoneInfo("UTC")).astimezone(tz)
            h = local.hour + local.minute / 60
            overnight = scenario.stop_hour > scenario.start_hour
            stopped = (h >= scenario.stop_hour or h < scenario.start_hour) if overnight else scenario.stop_hour <= h < scenario.start_hour
            # An overnight window belongs to the weekday on which it starts.
            anchor = local.date() - timedelta(days=1) if overnight and h < scenario.start_hour else local.date()
            if stopped and anchor.weekday() in scenario.weekdays:
                off += 1
        total_off += off
        baseline = max(0, latest + slope * evidence_age / 30.4375)
        demand = 1 + scenario.demand_growth_pct / 100 * offset / scenario.days
        baseline *= demand
        # Use only compute's share of the scoped run rate; retain storage and unknown charges.
        share = sum(float(plans[r.current_plan_id].compute_monthly_equivalent) for r in selected if r.current_plan_id in plans)
        estate = sum(float(r.monthly_cost or 0) for r in resources)
        reduction = baseline * min(1, share / estate) * off / 24 if estate else 0
        band = max(residual * 1.96, baseline * .10) * sqrt(1 + evidence_age / 30)
        points.append({"date": str(day), "baseline": round(baseline, 2), "scenario": round(max(0, baseline - reduction), 2),
                       "lower": round(max(0, baseline - band), 2), "upper": round(baseline + band, 2)})
    baseline_total = round(sum(p["baseline"] for p in points), 2)
    scenario_total = round(sum(p["scenario"] for p in points), 2)
    vcpu = sum(r.vcpu or 0 for r in resources if r.type == "vm" and r.status == "running")
    saved_hours = total_off * sum(r.vcpu or 0 for r in selected)
    baseline_energy = vcpu * scenario.days * 24 * scenario.watts_per_vcpu / 1000 * scenario.pue
    energy = saved_hours * scenario.watts_per_vcpu / 1000 * scenario.pue
    alerts = [a.model_dump(mode="json") for a in app.alerts(scope) if a.category in {"usage_anomaly", "data_quality"}]
    for r in resources:
        for metric in ("cpu", "memory"):
            observed = getattr(r, f"{metric}_p95")
            if observed is not None and observed * (1 + scenario.demand_growth_pct / 100) >= scenario.capacity_pct:
                alerts.append(dict(id=f"capacity-{r.id}-{metric}", category="capacity_pressure", severity="critical" if observed >= 95 else "warning",
                    resource_id=r.id, title=f"{r.name}: {metric} capacity risk", explanation=f"Historical p95 {observed:.1f}% projects to {observed * (1 + scenario.demand_growth_pct / 100):.1f}% against a {scenario.capacity_pct:g}% threshold. Review workload and headroom.", timestamp=str(cutoff)))
    if n >= 2:
        increase = (rates[-1] / rates[-2] - 1) * 100 if rates[-2] else (100 if rates[-1] else 0)
        if increase >= scenario.cost_increase_pct:
            alerts.append(dict(id="cost-growth", category="cost_increase", severity="warning", title="Cost run rate increased", explanation=f"Daily-normalized monthly billing rose {increase:.1f}% against a {scenario.cost_increase_pct:g}% threshold.", timestamp=str(cutoff)))
    if scenario.budget and sum(p["upper"] for p in points) > scenario.budget:
        alerts.append(dict(id="budget", category="budget_overrun", severity="critical" if baseline_total > scenario.budget else "warning", title="Potential horizon budget overrun", explanation=f"{scenario.days}-day baseline INR {baseline_total:,.2f}; budget INR {scenario.budget:,.2f}. Upper sensitivity total INR {sum(p['upper'] for p in points):,.2f}. Budget applies to this entire forecast horizon.", timestamp=str(cutoff)))
    usage = []
    indexed = {r.id: r for r in resources}
    with connect(app.database_path) as connection:
        for row in connection.execute("SELECT resource_id, AVG(cpu) AS cpu FROM metrics GROUP BY resource_id"):
            r = indexed.get(row["resource_id"])
            if r and row["cpu"] is not None and r.status == "running":
                usage.append((r.vcpu or 0) * row["cpu"] / 100)
    assumptions = [
        "Historical synthetic billing; forecasts cover the next days in the selected timezone, starting after both today and the billing cutoff. Older evidence widens the sensitivity range. Unknown prices are excluded.",
        "Daily cost trend uses linear regression over monthly daily-normalized billing. Band is a sensitivity range (at least ±10%), not a calibrated probability interval.",
        "Demand growth linearly scales cost; capacity extrapolates historical p95. These assumptions do not predict incidents or autoscaling behavior.",
        "Shutdown windows are evaluated hourly in the selected IANA timezone; overnight windows belong to their start weekday. Shutdown cost savings are conditional on hourly prorating. Quarterly commitments may yield zero invoice savings. Storage remains charged; dependencies and restart safety need review.",
        "Energy uses allocated vCPU × hours × assumed watts/vCPU × PUE; carbon uses assumed grid intensity. These are scenario estimates, not measured energy or verified emissions reductions.",
        "Role views are local presentation preferences, not authentication or tenant isolation. Existing team and source filters scope all projections.",
    ]
    return dict(as_of=str(cutoff), currency="INR", history=history, points=points, scenario=scenario.model_dump(),
        resource_count=len(resources), unknown_price_count=sum(r.monthly_cost is None for r in resources),
        baseline_total=baseline_total, scenario_total=scenario_total, conditional_savings=round(baseline_total - scenario_total, 2),
        selected_resources=[dict(id=r.id, name=r.name, vcpu=r.vcpu) for r in selected],
        usage=dict(allocated_vcpu_hours=vcpu * scenario.days * 24, avoided_vcpu_hours=saved_hours,
                   estimated_busy_vcpu_hours=round(sum(usage) * scenario.days * 24 * (1 + scenario.demand_growth_pct / 200), 1)),
        sustainability=dict(baseline_kwh=round(baseline_energy, 2), avoided_kwh=round(energy, 2), avoided_kg_co2e=round(energy * scenario.carbon_kg_per_kwh, 2)),
        alerts=sorted(alerts, key=lambda a: (a["severity"] != "critical", a["id"])), assumptions=assumptions)
