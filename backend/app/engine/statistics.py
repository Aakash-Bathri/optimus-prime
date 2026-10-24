from collections.abc import Sequence
from datetime import datetime
from math import floor
from statistics import fmean

from app.engine.policy import POLICY, Policy
from app.models.contracts import Analysis, DataQuality, MetricStatistics

METRICS = ("cpu", "memory", "disk", "iops", "network_in", "network_out")
UNITS = {"cpu": "%", "memory": "%", "disk": "%", "iops": "IOPS", "network_in": "Mbps", "network_out": "Mbps"}


def quantile(sorted_values: Sequence[float], probability: float) -> float:
    """Linear interpolation (type 7); caller supplies sorted finite observations."""
    index = (len(sorted_values) - 1) * probability
    lower = floor(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def summarize(values: list[float], unit: str) -> MetricStatistics:
    ordered = sorted(values)
    median = quantile(ordered, 0.5)
    mad = quantile(sorted(abs(value - median) for value in values), 0.5)
    ewma = values[0]
    for value in values[1:]:
        ewma = 0.1 * value + 0.9 * ewma
    outliers = sum(abs(value - median) > 6 * 1.4826 * mad for value in values) if mad else 0
    return MetricStatistics(
        count=len(values), mean=fmean(values), minimum=ordered[0], p50=median,
        p95=quantile(ordered, 0.95), p99=quantile(ordered, 0.99), maximum=ordered[-1],
        ewma=ewma, mad_outlier_count=outliers, unit=unit,
    )


def analyze(resource_id: str, rows: list[dict], start: datetime, end: datetime,
            interval_minutes: int, policy: Policy = POLICY, *,
            vcpu: int | None = None, memory_gib: float | None = None) -> Analysis:
    expected = int((end - start).total_seconds() / (interval_minutes * 60))
    values = {metric: [row[metric] for row in rows if row[metric] is not None] for metric in METRICS}
    valid_rows = [row for row in rows if all(row[metric] is not None for metric in METRICS)]
    latest = datetime.fromisoformat(valid_rows[-1]["timestamp"]) if valid_rows else None
    freshness = (end - latest).total_seconds() if latest else None
    coverage = len(valid_rows) / expected if expected else 0
    warnings = []
    if coverage < policy.minimum_coverage:
        warnings.append(f"Complete telemetry covers {coverage:.1%}; at least {policy.minimum_coverage:.0%} is required.")
    if freshness is None or freshness > policy.maximum_sample_age_seconds:
        warnings.append("Latest complete observation is stale or missing at the historical cutoff.")
    if (end - start).days < policy.minimum_history_days:
        warnings.append(f"At least {policy.minimum_history_days} days of history is required.")
    statistics = {metric: summarize(series, UNITS[metric]) for metric, series in values.items() if series}
    for metric, key, capacity, unit in (("cpu", "cpu_demand_cores", vcpu, "cores"), ("memory", "memory_demand_gib", memory_gib, "GiB")):
        if capacity is not None and metric in statistics:
            summary = statistics[metric].model_dump()
            for field in ("mean", "minimum", "p50", "p95", "p99", "maximum", "ewma"):
                summary[field] *= capacity / 100
            summary["unit"] = unit
            statistics[key] = MetricStatistics(**summary)
    return Analysis(
        resource_id=resource_id,
        quality=DataQuality(
            expected_samples=expected, observed_samples=len(rows), valid_samples=len(valid_rows),
            coverage=coverage, metric_coverage={metric: len(series) / expected if expected else 0 for metric, series in values.items()},
            latest_sample=latest, freshness_seconds=freshness, window_start=start, window_end=end,
            sufficient=not warnings, warnings=warnings,
        ),
        statistics=statistics,
    )
