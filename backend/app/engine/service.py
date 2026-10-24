import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from statistics import fmean

from app.database import connect
from app.engine.costs import money, sum_known
from app.engine.expenses import SOURCE_ID
from app.engine.optimizer import evaluate_candidate
from app.models.contracts import (
    Alert, DecisionRequest, ProviderPlan, Recommendation, RecommendationSummary, Resource, SimulationRequest,
)
from app.repositories.estate import read_analysis


class DecisionConflict(Exception):
    pass


@dataclass(frozen=True)
class Filters:
    environment: str | None = None
    region: str | None = None
    team: str | None = None
    resource_type: str | None = None
    search: str | None = None
    data_source: str | None = None

    def matches(self, resource: Resource) -> bool:
        return (
            (self.data_source is None or self.data_source == SOURCE_ID)
            and (self.environment is None or resource.environment == self.environment)
            and (self.region is None or resource.region == self.region)
            and (self.team is None or (resource.team or "Unassigned") == self.team)
            and (self.resource_type is None or resource.type == self.resource_type)
            and (not self.search or self.search.casefold() in f"{resource.id} {resource.name}".casefold())
        )


class CloudPilot:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def dataset(self) -> dict:
        with connect(self.database_path) as connection:
            return json.loads(connection.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()["payload"])

    def resources(self, filters: Filters = Filters()) -> list[Resource]:
        with connect(self.database_path) as connection:
            resources = [Resource.model_validate_json(row["payload"]) for row in connection.execute("SELECT payload FROM resources ORDER BY id")]
        return [resource for resource in resources if filters.matches(resource)]

    def resource(self, resource_id: str) -> Resource:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT payload FROM resources WHERE id=?", (resource_id,)).fetchone()
        if row is None:
            raise LookupError("Resource not found")
        return Resource.model_validate_json(row["payload"])

    def detail(self, resource_id: str) -> dict:
        resource = self.resource(resource_id)
        with connect(self.database_path) as connection:
            analysis = read_analysis(connection, resource_id)
            relationships = [json.loads(row["payload"]) for row in connection.execute(
                "SELECT payload FROM relationships WHERE json_extract(payload,'$.source_resource_id')=? OR json_extract(payload,'$.target_resource_id')=?", (resource_id, resource_id))]
            events = [json.loads(row["payload"]) for row in connection.execute("SELECT payload FROM events WHERE resource_id=?", (resource_id,))]
            gpu = dict(connection.execute("SELECT COUNT(*) AS samples, AVG(utilization) AS mean_utilization, MAX(utilization) AS peak_utilization, MAX(memory_pct) AS peak_memory_pct, MAX(memory_gib) AS peak_memory_gib FROM gpu_metrics WHERE resource_id=?", (resource_id,)).fetchone()) if resource.type == "gpu" else None
        return dict(resource.model_dump(mode="json"), analysis=analysis.model_dump(mode="json") if analysis else None,
                    relationships=relationships, events=events, gpu_statistics=gpu)

    def plans(self) -> list[ProviderPlan]:
        with connect(self.database_path) as connection:
            return [ProviderPlan.model_validate_json(row["payload"]) for row in connection.execute("SELECT payload FROM plans ORDER BY id")]

    @staticmethod
    def _apply_decision(recommendation, row):
        if row["decision"] is not None:
            recommendation.decision = row["decision"]
            recommendation.decision_revision = row["revision"]
            recommendation.decided_at = datetime.fromisoformat(row["decided_at"])
        return recommendation

    def recommendations(self, filters: Filters = Filters(), *, outcome: str | None = None,
                        decision: str | None = None, action: str | None = None) -> list[RecommendationSummary]:
        resource_ids = {resource.id for resource in self.resources(filters)}
        with connect(self.database_path) as connection:
            rows = connection.execute("SELECT r.summary, r.resource_id, d.decision, d.revision, d.decided_at FROM recommendations r LEFT JOIN decisions d ON d.recommendation_id=r.id ORDER BY r.id")
            results = [self._apply_decision(RecommendationSummary.model_validate_json(row["summary"]), row) for row in rows if row["resource_id"] in resource_ids]
        results = [item for item in results if (outcome is None or item.outcome == outcome) and
                   (decision is None or item.decision == decision) and (action is None or item.action == action)]
        return sorted(results, key=lambda item: (
            item.outcome in {"no_action", "unsupported"}, item.decision == "rejected",
            -(item.conditional_monthly_savings or item.modeled_monthly_savings or Decimal(0)), item.id,
        ))

    def recommendation(self, recommendation_id: str) -> Recommendation:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT r.payload, d.decision, d.revision, d.decided_at FROM recommendations r LEFT JOIN decisions d ON d.recommendation_id=r.id WHERE r.id=?", (recommendation_id,)).fetchone()
            if row is None:
                raise LookupError("Recommendation not found in this dataset version")
            return self._apply_decision(Recommendation.model_validate_json(row["payload"]), row)

    def decide(self, recommendation_id: str, request: DecisionRequest) -> Recommendation:
        with connect(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM recommendations WHERE id=?", (recommendation_id,)).fetchone()
            if row is None:
                raise LookupError("Recommendation not found in this dataset version")
            recommendation = Recommendation.model_validate_json(row["payload"])
            decision = connection.execute("SELECT * FROM decisions WHERE recommendation_id=?", (recommendation_id,)).fetchone()
            revision = decision["revision"] if decision else 0
            previous = decision["decision"] if decision else "pending"
            if request.version != recommendation.version or request.expected_revision != revision:
                raise DecisionConflict("Evidence or decision changed. Refresh the finding before updating it.")
            if request.decision == "accepted" and recommendation.outcome in {"no_action", "unsupported", "insufficient_data"}:
                raise DecisionConflict("This outcome has no plan action. Restore evidence or select a review finding.")
            if request.decision == "accepted" and recommendation.ready:
                # Financial actions cannot overlap. Review-only findings do not
                # alter the resource configuration or authorize execution.
                for other in connection.execute("SELECT r.summary FROM recommendations r JOIN decisions d ON d.recommendation_id=r.id WHERE r.resource_id=? AND r.id<>? AND d.decision='accepted'", (recommendation.resource_id, recommendation_id)):
                    if RecommendationSummary.model_validate_json(other["summary"]).ready:
                        raise DecisionConflict("A financially effective action is already selected for this resource.")
            if previous != request.decision:
                now = datetime.now(timezone.utc).isoformat()
                connection.execute("INSERT INTO decisions VALUES (?,?,?,?) ON CONFLICT(recommendation_id) DO UPDATE SET decision=excluded.decision, revision=excluded.revision, decided_at=excluded.decided_at",
                                   (recommendation_id, request.decision, revision + 1, now))
                connection.execute("INSERT INTO audit (recommendation_id,actor,previous_decision,decision,timestamp,version) VALUES (?,?,?,?,?,?)",
                                   (recommendation_id, "local-engineer", previous, request.decision, now, recommendation.version))
        return self.recommendation(recommendation_id)

    def series(self, resource_ids: list[str], resolution: str = "day") -> dict:
        metadata = self.dataset()
        start = datetime.fromisoformat(metadata["window_start"])
        end = datetime.fromisoformat(metadata["analysis_as_of"])
        bucket_format = "%Y-%m-%dT00:00:00+00:00" if resolution == "day" else "%Y-%m-%dT%H:00:00+00:00"
        columns = ["COUNT(*) AS samples", "SUM(CASE WHEN cpu IS NOT NULL AND memory IS NOT NULL AND disk IS NOT NULL AND iops IS NOT NULL AND network_in IS NOT NULL AND network_out IS NOT NULL THEN 1 ELSE 0 END) AS valid_samples"]
        for metric in ("cpu", "memory", "disk", "iops", "network_in", "network_out"):
            columns.extend([f"AVG({metric}) AS {metric}", f"MAX({metric}) AS {metric}_peak"])
        with connect(self.database_path) as connection:
            placeholders = ",".join("?" for _ in resource_ids) or "NULL"
            rows = connection.execute(f"SELECT strftime(?,timestamp) AS bucket, {','.join(columns)} FROM metrics WHERE resource_id IN ({placeholders}) GROUP BY bucket ORDER BY bucket", [bucket_format, *resource_ids])
            indexed = {row["bucket"]: dict(row) for row in rows}
        step = timedelta(days=1) if resolution == "day" else timedelta(hours=1)
        points = []
        when = start
        while when < end:
            point = indexed.get(when.isoformat(), {"bucket": when.isoformat(), "samples": 0, "valid_samples": 0})
            point["timestamp"] = point.pop("bucket")
            point["expected_samples"] = int(step.total_seconds() / (metadata["interval_minutes"] * 60)) * len(resource_ids)
            points.append(point)
            when += step
        return {"resolution": resolution, "timezone": "UTC (assumed)", "aggregation": "Mean and maximum per bucket; nulls retained", "points": points}

    def billing_history(self, resource_ids: set[str]) -> list[dict]:
        totals: dict[str, Decimal] = {}
        with connect(self.database_path) as connection:
            for row in connection.execute("SELECT * FROM billing ORDER BY month"):
                if row["resource_id"] in resource_ids:
                    totals[row["month"]] = totals.get(row["month"], Decimal(0)) + Decimal(row["amount"])
        return [{"month": month, "amount": str(money(total)), "synthetic": True} for month, total in totals.items()]

    def alerts(self, filters: Filters = Filters()) -> list[Alert]:
        resource_ids = {resource.id for resource in self.resources(filters)}
        with connect(self.database_path) as connection:
            alerts = [Alert.model_validate_json(row["payload"]) for row in connection.execute("SELECT payload FROM alerts")]
        alerts = [alert for alert in alerts if alert.resource_id in resource_ids]
        history = self.billing_history(resource_ids)
        if len(history) >= 2:
            def daily_rate(item):
                year, month = map(int, item["month"].split("-"))
                return Decimal(item["amount"]) / monthrange(year, month)[1]
            previous, latest = daily_rate(history[-2]), daily_rate(history[-1])
            increase = (latest / previous - 1) * 100 if previous else None
            if (increase is not None and increase >= 5) or (previous == 0 and latest > 0):
                growth = f"Daily cost rose {increase:.1f}%" if increase is not None else "Billed cost appeared from a zero baseline"
                alerts.append(Alert(
                    id="cost-increase", category="cost_increase", severity="warning", title="Synthetic billing is rising",
                    explanation=f"{growth} from {history[-2]['month']} to {history[-1]['month']}. This is a generated billing scenario, not an invoice or verified forecast.",
                    timestamp=history[-1]["month"] + "-01T00:00:00+00:00", observed=float(latest), baseline=float(previous), threshold=5,
                    unit="INR/day; alert threshold 5% growth", source="synthetic_billing",
                ))
        severity = {"critical": 0, "warning": 1, "info": 2}
        return sorted(alerts, key=lambda alert: (severity[alert.severity], alert.id))

    def plan(self, filters: Filters = Filters()) -> dict:
        resources = self.resources(filters)
        items = [item for item in self.recommendations(filters) if item.decision == "accepted"]
        target_costs = {resource.id: resource.monthly_cost for resource in resources}
        for item in items:
            if item.ready and not item.review_only:
                target_costs[item.resource_id] = item.target_monthly_cost
        current = sum_known([resource.monthly_cost for resource in resources])
        projected = sum_known(list(target_costs.values()))
        breakdown = []
        for environment in ("production", "staging", "development"):
            members = [resource for resource in resources if resource.environment == environment]
            before = sum_known([resource.monthly_cost for resource in members])
            after = sum_known([target_costs[resource.id] for resource in members])
            breakdown.append({"environment": environment, "current_cost": str(before), "projected_cost": str(after), "savings": str(money(before - after)), "unknown_price_count": sum(resource.monthly_cost is None for resource in members)})
        return {
            "currency": "INR", "current_monthly_cost": str(current), "projected_monthly_cost": str(projected),
            "accepted_monthly_savings": str(money(current - projected)), "verified_savings": None,
            "unknown_price_count": sum(resource.monthly_cost is None for resource in resources),
            "items": [item.model_dump(mode="json") for item in items], "by_environment": breakdown,
            "review_only_count": sum(item.review_only for item in items),
            "effective_action_count": sum(item.ready and not item.review_only for item in items),
            "note": "Review-only items do not change projected cost. Plan acceptance never executes infrastructure changes.",
        }

    def summary(self, filters: Filters = Filters()) -> dict:
        resources = self.resources(filters)
        recommendations = self.recommendations(filters)
        actionable = [item for item in recommendations if item.outcome in {"recommendation", "blocked", "insufficient_data"}]
        conditional: dict[str, Decimal] = {}
        for item in recommendations:
            if item.decision != "rejected" and item.conditional_monthly_savings is not None:
                conditional[item.resource_id] = max(conditional.get(item.resource_id, Decimal(0)), item.conditional_monthly_savings)
        groups = {}
        for field in ("environment", "region", "team"):
            members_by_key: dict[str, list[Resource]] = {}
            for resource in resources:
                members_by_key.setdefault(getattr(resource, field) or "Unassigned", []).append(resource)
            groups[field] = [{"name": key, "cost": str(sum_known([resource.monthly_cost for resource in members])), "count": len(members),
                              "unknown_price_count": sum(resource.monthly_cost is None for resource in members)} for key, members in sorted(members_by_key.items())]
        cpus = [resource.cpu_p95 for resource in resources if resource.cpu_p95 is not None]
        memory = [resource.memory_p95 for resource in resources if resource.memory_p95 is not None]
        return {
            "resource_count": len(resources), "vm_count": sum(resource.type == "vm" for resource in resources),
            "known_monthly_cost": str(sum_known([resource.monthly_cost for resource in resources])),
            "unknown_price_count": sum(resource.monthly_cost is None for resource in resources),
            "conditional_monthly_savings": str(sum_known(list(conditional.values()))),
            "recommendation_count": len(actionable), "ready_count": sum(item.ready for item in recommendations),
            "insufficient_data_count": sum(item.outcome == "insufficient_data" for item in recommendations),
            "avg_cpu_p95": fmean(cpus) if cpus else None, "avg_memory_p95": fmean(memory) if memory else None,
            "breakdown": groups, "plan": self.plan(filters),
            "billing_history": self.billing_history({resource.id for resource in resources}),
            "alerts": [alert.model_dump(mode="json") for alert in self.alerts(filters)[:5]],
            "alert_count": len(self.alerts(filters)),
            "priority_recommendations": [item.model_dump(mode="json") for item in actionable[:5]],
        }

    def simulate(self, request: SimulationRequest) -> dict:
        resource = self.resource(request.resource_id)
        if resource.type != "vm":
            raise DecisionConflict("Capacity simulation currently supports VMs only")
        plan = next((plan for plan in self.plans() if plan.id == request.target_plan_id), None)
        if plan is None:
            raise LookupError("Catalog plan not found")
        with connect(self.database_path) as connection:
            analysis = read_analysis(connection, resource.id)
            rows = [dict(row) for row in connection.execute("SELECT * FROM metrics WHERE resource_id=? ORDER BY timestamp", (resource.id,))]
            has_gpu = connection.execute("SELECT 1 FROM relationships WHERE json_extract(payload,'$.source_resource_id')=? AND json_extract(payload,'$.relationship_type')='attached_gpu'", (resource.id,)).fetchone() is not None
        if analysis is None:
            raise DecisionConflict("Telemetry is unavailable for simulation")
        candidate = evaluate_candidate(resource, plan, analysis, rows, has_gpu=has_gpu, multiplier=request.demand_multiplier)
        return {"resource_id": resource.id, "demand_multiplier": request.demand_multiplier,
                "candidate": candidate.model_dump(mode="json"), "mode": "modeled", "verified_savings": None,
                "note": "Simulation is read-only; it neither accepts a plan nor validates a live workload."}

    def export(self, filters: Filters = Filters()) -> dict:
        plan = self.plan(filters)
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset": self.dataset(), "plan": plan,
                "evidence": [self.recommendation(item["id"]).model_dump(mode="json") for item in plan["items"]]}

    def audit(self, limit: int = 100) -> list[dict]:
        with connect(self.database_path) as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]
