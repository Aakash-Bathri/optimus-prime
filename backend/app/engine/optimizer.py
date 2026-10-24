from datetime import datetime
from decimal import Decimal

from app.engine.costs import money, stop_savings
from app.engine.policy import POLICY, Policy
from app.models.contracts import (
    Analysis, CandidateEvaluation, Check, ProviderPlan, Provenance,
    Recommendation, Replay, Resource,
)


def check(code: str, passed: bool | None, message: str, actual=None, limit=None, unit=None) -> Check:
    return Check(code=code, status="unknown" if passed is None else "passed" if passed else "failed",
                 message=message, actual=actual, limit=limit, unit=unit)


def replay(rows: list[dict], cpu_ratio: float, memory_ratio: float,
           expected: int, policy: Policy = POLICY, interval_seconds: float = 900) -> Replay:
    cpu_breaches = memory_breaches = breaches = stress = longest = consecutive = valid = 0
    previous = None
    for row in rows:
        if row["cpu"] is None or row["memory"] is None:
            consecutive, previous = 0, None
            continue
        valid += 1
        cpu = row["cpu"] * cpu_ratio
        memory = row["memory"] * memory_ratio
        cpu_fail = cpu > policy.cpu_limit_pct + 1e-9
        memory_fail = memory > policy.memory_limit_pct + 1e-9
        cpu_breaches += cpu_fail
        memory_breaches += memory_fail
        breached = cpu_fail or memory_fail
        breaches += breached
        stress += (cpu * policy.stress_multiplier > policy.cpu_limit_pct + 1e-9 or
                   memory * policy.stress_multiplier > policy.memory_limit_pct + 1e-9)
        # Timestamp gaps interrupt runs, even when the missing row is absent entirely.
        when = datetime.fromisoformat(row["timestamp"])
        if previous is not None and (when - previous).total_seconds() != interval_seconds:
            consecutive = 0
        consecutive = consecutive + 1 if breached else 0
        longest = max(longest, consecutive)
        previous = when
    return Replay(
        sample_count=valid, missing_samples=max(expected - valid, 0), cpu_breaches=cpu_breaches,
        memory_breaches=memory_breaches, breached_samples=breaches, longest_breach_samples=longest,
        stress_breached_samples=stress, stress_multiplier=policy.stress_multiplier,
    )


def evaluate_candidate(resource: Resource, plan: ProviderPlan, analysis: Analysis, rows: list[dict],
                       *, has_gpu: bool = False, multiplier: float = 1,
                       historical_snapshot: bool = True, policy: Policy = POLICY) -> CandidateEvaluation:
    cpu_ratio = (resource.vcpu or 0) / plan.vcpu * multiplier
    memory_ratio = (resource.memory_gib or 0) / plan.memory_gib * multiplier
    stats = analysis.statistics

    def projected(metric: str, field: str, ratio: float):
        return getattr(stats[metric], field) * ratio if metric in stats else None

    cpu_peak = projected("cpu", "maximum", cpu_ratio)
    memory_peak = projected("memory", "maximum", memory_ratio)
    compatible = resource.hardware == plan.hardware and resource.instance_family == plan.instance_family
    checks = [
        check("hardware", resource.hardware == plan.hardware, "Hardware class must match; per-core performance is not interchangeable."),
        check("family", resource.instance_family == plan.instance_family, "Workload family must match."),
        check("storage_type", resource.storage_type == plan.storage_type, "Storage attachment mode must match."),
        check("coverage", analysis.quality.sufficient, "All required telemetry must meet coverage, history and cutoff freshness rules.", analysis.quality.coverage, policy.minimum_coverage, "fraction"),
        check("cpu_peak", None if cpu_peak is None else cpu_peak <= policy.cpu_limit_pct + 1e-9,
              "Observed CPU peak must retain configured headroom.", cpu_peak, policy.cpu_limit_pct, "%"),
        check("memory_peak", None if memory_peak is None else memory_peak <= policy.memory_limit_pct + 1e-9,
              "Observed memory peak must retain configured headroom.", memory_peak, policy.memory_limit_pct, "%"),
    ]
    disk_known = resource.disk_gb is not None and plan.disk_gb is not None
    checks.append(check("disk_no_shrink", plan.disk_gb >= resource.disk_gb if disk_known else None,
                        "Disk shrinking is unsupported; unknown AMD disk bundling needs verification.", plan.disk_gb, resource.disk_gb, "GB"))
    disk_peak = stats["disk"].maximum * resource.disk_gb / plan.disk_gb if disk_known and "disk" in stats else None
    checks.append(check("disk_occupancy", None if disk_peak is None else disk_peak <= policy.disk_limit_pct,
                        "Peak disk occupancy must retain headroom.", disk_peak, policy.disk_limit_pct, "%"))
    allowance_known = resource.transfer_allowance_gb is not None and plan.transfer_allowance_gb is not None
    checks.append(check("transfer_allowance", plan.transfer_allowance_gb >= resource.transfer_allowance_gb if allowance_known else None,
                        "Do not downgrade the included transfer allowance.", plan.transfer_allowance_gb, resource.transfer_allowance_gb, "GB"))
    saturated_downsize = "cpu" in stats and stats["cpu"].maximum >= policy.saturation_pct and plan.vcpu < (resource.vcpu or 0)
    checks.append(check("saturation", not saturated_downsize, "Observed CPU saturation hides latent demand and blocks downsizing."))
    interval_seconds = (analysis.quality.window_end - analysis.quality.window_start).total_seconds() / analysis.quality.expected_samples
    historical = replay(rows, cpu_ratio, memory_ratio, analysis.quality.expected_samples, policy, interval_seconds) if compatible else None
    checks.append(check("historical_replay", None if historical is None else historical.breached_samples == 0,
                        "No modeled CPU/memory threshold breaches in observed samples.", historical.breached_samples if historical else None, 0, "samples"))
    checks.append(check("stress_replay", None if historical is None else historical.stress_breached_samples == 0,
                        f"A {policy.stress_multiplier:g}× demand scenario must retain the same headroom.", historical.stress_breached_samples if historical else None, 0, "samples"))
    network_peak = max((row["network_in"] + row["network_out"] for row in rows
                        if row["network_in"] is not None and row["network_out"] is not None), default=None)
    iops_peak = stats["iops"].maximum if "iops" in stats else None
    checks.extend([
        check("iops_capacity", None if plan.iops_limit is None or iops_peak is None else iops_peak * multiplier <= plan.iops_limit,
              "Provider IOPS capability is required; transfer allowance does not specify IOPS.", iops_peak * multiplier if iops_peak is not None else None, plan.iops_limit, "IOPS"),
        check("network_capacity", None if plan.network_mbps_limit is None or network_peak is None else network_peak * multiplier <= plan.network_mbps_limit,
              "Provider network throughput capability is required; monthly transfer is a different unit.", network_peak * multiplier if network_peak is not None else None, plan.network_mbps_limit, "Mbps"),
        check("region_availability", resource.region == plan.region if plan.region_verified and plan.region else None,
              "Regional availability/tariff has not been independently verified.", resource.region, plan.region),
        check("price_provenance", True if plan.pricing_verified else None, "User-supplied prices require independent verification."),
        check("resize_support", True if plan.resize_verified else None, "Provider resize support and interruption behavior require verification."),
        check("storage_compatibility", True if plan.storage_verified else None, "Disk bundling and retained attachments require provider verification."),
        check("gpu_compatibility", None if has_gpu else True, "Attached accelerator compatibility must be verified before changing its host."),
        check("live_evidence", None if historical_snapshot else True, "Historical synthetic telemetry cannot authorize a live change."),
    ])
    capacity_codes = {"hardware", "family", "storage_type", "coverage", "cpu_peak", "memory_peak", "saturation", "historical_replay", "stress_replay"}
    capacity_eligible = all(item.status == "passed" for item in checks if item.code in capacity_codes)
    return CandidateEvaluation(
        plan=plan, checks=checks, capacity_eligible=capacity_eligible,
        eligible=all(item.status == "passed" for item in checks),
        monthly_cost=plan.compute_monthly_equivalent,
        monthly_savings=money(resource.monthly_cost - plan.compute_monthly_equivalent) if resource.monthly_cost is not None else None,
        projected_cpu_p99=projected("cpu", "p99", cpu_ratio), projected_cpu_peak=cpu_peak,
        projected_memory_p99=projected("memory", "p99", memory_ratio), projected_memory_peak=memory_peak,
        replay=historical,
    )


def base_recommendation(resource: Resource, provenance: Provenance, action: str, **kwargs) -> Recommendation:
    fields = dict(
        id=f"rec-{resource.id}-{action}-{provenance.dataset_version[:10]}", version=provenance.dataset_version,
        resource_id=resource.id, resource_name=resource.name, environment=resource.environment,
        region=resource.region, team=resource.team, action=action, outcome="blocked", risk="unknown",
        ready=False, review_only=True, current_plan_id=resource.current_plan_id, target_plan_id=None,
        current_monthly_cost=resource.monthly_cost, target_monthly_cost=None,
        modeled_monthly_savings=None, conditional_monthly_savings=None, blockers=[], prerequisites=[],
        provenance=provenance,
    )
    fields.update(kwargs)
    return Recommendation(**fields)


def optimize(resource: Resource, plans: list[ProviderPlan], analysis: Analysis | None, rows: list[dict],
             provenance: Provenance, has_gpu: bool = False) -> list[Recommendation]:
    if resource.type != "vm":
        if resource.lifecycle_state in {"unattached", "unassociated"}:
            return [base_recommendation(
                resource, provenance, "orphan_review", title="Review an unassigned resource",
                explanation="Inventory has no active attachment. Ownership, retention and dependencies must be resolved before removal.",
                target_monthly_cost=Decimal("0.00") if resource.monthly_cost is not None else None,
                conditional_monthly_savings=resource.monthly_cost,
                blockers=["Owner/dependency and retention review is incomplete.", "No deletion or release is authorized."] +
                         (["Public-IP pricing is unknown; cash savings cannot be calculated."] if resource.monthly_cost is None else []),
                prerequisites=["Confirm ownership and dependency history.", "Confirm backup/retention disposition.", "Verify provider pricing and removal behavior."],
            )]
        return [base_recommendation(
            resource, provenance, "observe", outcome="unsupported" if resource.type == "gpu" else "no_action",
            title="Accelerator analysis needs provider data" if resource.type == "gpu" else "Retain the attached resource",
            explanation="GPU telemetry is available, but device compatibility and prices are unknown." if resource.type == "gpu" else
                        "The resource has an attachment; removal is not inferred from inventory alone.",
            blockers=["GPU price/capability catalog is unavailable."] if resource.type == "gpu" else [],
        )]
    if analysis is None or not analysis.quality.sufficient:
        return [base_recommendation(
            resource, provenance, "observe", outcome="insufficient_data", title="Restore telemetry before sizing",
            explanation="Missing, invalid or stale samples prevent a defensible capacity recommendation.",
            analysis=analysis, blockers=analysis.quality.warnings if analysis else ["VM telemetry is missing."],
            prerequisites=["Restore complete observations and rerun analysis."],
        )]

    candidates = [evaluate_candidate(resource, plan, analysis, rows, has_gpu=has_gpu) for plan in plans]
    candidates.sort(key=lambda candidate: (candidate.monthly_cost, candidate.plan.id))
    eligible = [candidate for candidate in candidates if candidate.eligible]
    review = [candidate for candidate in candidates if candidate.capacity_eligible and
              not any(item.status == "failed" for item in candidate.checks)]
    # Unknown gates allow investigation, never eligible selection or accepted savings.
    selected = eligible[0] if eligible else review[0] if review else None
    stats = analysis.statistics
    pressure = stats["cpu"].maximum > POLICY.cpu_limit_pct or stats["memory"].maximum > POLICY.memory_limit_pct
    beneficial = selected is not None and selected.plan.id != resource.current_plan_id and (
        pressure or (selected.monthly_savings is not None and selected.monthly_savings > 0)
    )
    if beneficial:
        ready = selected.eligible
        action = "capacity_review" if selected.monthly_savings is not None and selected.monthly_savings < 0 else "resize"
        blocked = [item.message for item in selected.checks if item.status != "passed"]
        result = base_recommendation(
            resource, provenance, action, outcome="recommendation" if ready else "blocked", ready=ready,
            review_only=not ready, title="Review capacity headroom" if action == "capacity_review" else "Review a smaller configuration",
            explanation=f"{selected.plan.id} passes CPU/RAM peak and stress checks. " +
                        ("All implemented provider gates pass." if ready else "Provider and data-verification gates still block an actionable resize."),
            target_plan_id=selected.plan.id, target_monthly_cost=selected.monthly_cost,
            modeled_monthly_savings=selected.monthly_savings if ready else None,
            conditional_monthly_savings=None if ready else selected.monthly_savings,
            risk="high" if pressure else "moderate", blockers=blocked,
            prerequisites=["Verify current inventory and live telemetry.", "Resolve every unknown capability and tariff.", "Review interruption/rollback requirements before a separate change approval."],
            analysis=analysis, candidates=candidates, checks=selected.checks,
        )
    else:
        result = base_recommendation(
            resource, provenance, "observe", outcome="blocked" if pressure else "no_action",
            title="Capacity constraints need review" if pressure else "No supported lower-cost change",
            explanation="No catalog alternative passes the observed peak/stress and known compatibility checks." if not selected else
                        "No cheaper alternative satisfies the implemented capacity and known storage constraints.",
            risk="high" if pressure else "low", analysis=analysis, candidates=candidates,
            blockers=["Provider capabilities and live freshness remain unverified."] if pressure else [],
        )
    results = [result]
    idle = (stats["cpu"].maximum <= POLICY.idle_cpu_peak_pct and
            stats["memory"].maximum <= POLICY.idle_memory_peak_pct and
            stats["iops"].maximum <= POLICY.idle_iops_peak and
            stats["network_in"].maximum + stats["network_out"].maximum <= POLICY.idle_network_peak_mbps)
    if idle:
        results.append(base_recommendation(
            resource, provenance, "idle_review", title="Investigate sustained inactivity",
            explanation="CPU, memory, disk activity and network peaks are low across the full observation window. Stopping alone has no cash benefit under this tariff.",
            risk="high" if resource.environment == "production" else "moderate", analysis=analysis,
            conditional_monthly_savings=stop_savings(resource.monthly_cost), target_monthly_cost=resource.monthly_cost,
            blockers=["Ownership/dependency and retention review is required.", "Stopped VMs remain billable; deletion economics need separate verification."],
            prerequisites=["Confirm the workload is dispensable, including batch and seasonal obligations.", "Review backups and provider deletion behavior."],
        ))
    return results
