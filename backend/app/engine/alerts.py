from collections import defaultdict
from datetime import datetime
from statistics import median

from app.engine.policy import POLICY
from app.models.contracts import Alert, Analysis, Resource


def resource_alerts(resource: Resource, analysis: Analysis, rows: list[dict]) -> list[Alert]:
    alerts = []
    cutoff = analysis.quality.window_end
    identity = dict(resource_id=resource.id, resource_name=resource.name, source="synthetic_telemetry")
    if not analysis.quality.sufficient:
        alerts.append(Alert(
            id=f"quality-{resource.id}", category="data_quality", severity="warning", title="Incomplete resource telemetry",
            explanation=" ".join(analysis.quality.warnings), timestamp=cutoff,
            observed=analysis.quality.coverage * 100, baseline=100, threshold=POLICY.minimum_coverage * 100, unit="% coverage", **identity,
        ))
    for metric, unit, floor_value in (("cpu", "% CPU", 40), ("iops", "IOPS", 100)):
        stats = analysis.statistics.get(metric)
        if not stats:
            continue
        observed_rows = [row for row in rows if row[metric] is not None]
        seasonal = defaultdict(list)
        for row in observed_rows:
            seasonal[row["timestamp"][11:16]].append(row[metric])
        baselines = {slot: median(values) for slot, values in seasonal.items()}
        thresholds = {slot: max(floor_value, baselines[slot] * 3,
                                baselines[slot] + 6 * 1.4826 * median(abs(value - baselines[slot]) for value in values))
                      for slot, values in seasonal.items()}
        high = [row for row in observed_rows if len(seasonal[row["timestamp"][11:16]]) >= 7 and row[metric] > thresholds[row["timestamp"][11:16]]]
        high_times = {row["timestamp"] for row in high}
        interval = (analysis.quality.window_end - analysis.quality.window_start).total_seconds() / analysis.quality.expected_samples
        consecutive = longest = 0
        previous = None
        for row in rows:
            when = datetime.fromisoformat(row["timestamp"])
            if previous is not None and (when - previous).total_seconds() != interval:
                consecutive = 0
            consecutive = consecutive + 1 if row["timestamp"] in high_times else 0
            longest = max(longest, consecutive)
            previous = when
        # Same-time-of-day baselines preserve regular batch/burst patterns.
        if longest * interval >= 4 * 3600 and len(high) <= len(observed_rows) * 0.1:
            peak = max(high, key=lambda row: row[metric])
            slot = peak["timestamp"][11:16]
            alerts.append(Alert(
                id=f"anomaly-{resource.id}-{metric}", category="usage_anomaly", severity="warning",
                title=f"Unusual {metric.upper()} demand", timestamp=peak["timestamp"],
                explanation=f"{len(high)} observations exceed same-time-of-day median/MAD thresholds, including at least 4 consecutive hours. Regular daily patterns inform the baseline. This is a statistical finding, not an incident diagnosis.",
                observed=peak[metric], baseline=baselines[slot], threshold=thresholds[slot], unit=unit, **identity,
            ))
    for metric in ("cpu", "memory"):
        stats = analysis.statistics.get(metric)
        if stats and (stats.p95 > 80 or stats.maximum >= 95):
            alerts.append(Alert(
                id=f"pressure-{resource.id}-{metric}", category="capacity_pressure", severity="critical" if stats.p95 > 90 else "warning",
                title=f"{metric.title()} headroom needs review", timestamp=cutoff,
                explanation=f"Observed p95 is {stats.p95:.1f}% and peak is {stats.maximum:.1f}%. Capacity pressure is evaluated independently from savings.",
                observed=stats.maximum, baseline=stats.p95, threshold=80, unit=f"% {metric}", **identity,
            ))
    return alerts
