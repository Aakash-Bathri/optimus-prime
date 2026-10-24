"""Read only the delivered source contracts; outcome labels are never inputs."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.engine.costs import money, monthly_equivalent
from app.engine.policy import ENGINE_VERSION, POLICY
from app.models.contracts import ProviderPlan, Resource

SOURCE_FILES = (
    "assumptions.json", "resources.csv", "pricing_catalog.csv", "pricing.csv",
    "metrics.csv", "gpu_metrics.csv", "resource_relationships.csv", "events.csv",
    "billing_history.csv", "data_quality_summary.json",
)
# Only code that produces the stored import/analysis belongs to its identity.
ANALYSIS_PATHS = (
    "adapters/dataset.py", "repositories/estate.py", "models/contracts.py",
    "engine/alerts.py", "engine/costs.py", "engine/optimizer.py",
    "engine/policy.py", "engine/statistics.py",
)
CSV_METRICS = {
    "cpu": "cpu_utilization_pct", "memory": "memory_utilization_pct",
    "disk": "disk_used_pct", "iops": "disk_iops",
    "network_in": "network_in_mbps", "network_out": "network_out_mbps",
}
ASSUMPTIONS = [
    "Synthetic inventory, workloads, relationships and billing; no provider connection.",
    "Naive source timestamps are assumed UTC; the original timezone is unverified.",
    "Analysis uses the historical dataset cutoff, not live telemetry freshness.",
    "VM capacity is assumed unchanged across this synthetic window; no resize history is supplied.",
    "RAM follows the manifest's GiB convention; disk capacities retain source GB units.",
    "Monthly compute equivalent = quarterly commitment total / 3; not a monthly tariff.",
    "Powered-off VMs remain billable: stop-only and schedule cash savings are zero.",
    "GPU and public-IP prices are unknown; known-cost totals exclude these charges.",
    "Prices are a user-supplied snapshot, not independently verified; GST and discounts excluded.",
    "Same-family linear capacity projection is an approximation; replay is not a workload benchmark.",
    "Region, resize, storage, IOPS/network and attached-GPU compatibility need verification.",
    "Verified savings are unavailable without an applied change and actual billing reconciliation.",
]


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def number(value: str) -> float | None:
    if not value.strip():
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite numeric source value")
    return result


def amount(value: str) -> Decimal | None:
    if not value.strip():
        return None
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid monetary source value") from None
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid monetary source value")
    return result


def records(path: Path, required: set[str]):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if not headers or any(not header.strip() for header in headers) or len(headers) != len(set(headers)):
            raise ValueError(f"{path.name}: duplicate or empty CSV column name")
        if not required <= set(headers):
            raise ValueError(f"{path.name}: missing columns {sorted(required - set(reader.fieldnames or []))}")
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name}:{line}: malformed CSV row")
            yield row


def unique(rows: list[dict], key: str, source: str) -> dict[str, dict]:
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows) or any(not value.strip() or value != value.strip() for value in indexed):
        raise ValueError(f"{source}: duplicate or empty {key}")
    return indexed


class DatasetSource:
    def __init__(self, path: Path):
        self.path = path
        self.file_hashes = {}
        for name in SOURCE_FILES:
            digest = hashlib.sha256()
            with (path / name).open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            self.file_hashes[name] = digest.hexdigest()
        app_root = Path(__file__).resolve().parents[1]
        implementation = hashlib.sha256()
        for relative in sorted(ANALYSIS_PATHS):
            implementation.update(relative.encode() + b"\0")
            implementation.update(hashlib.sha256((app_root / relative).read_bytes()).digest())
        code_hash = implementation.hexdigest()
        self.implementation_hash = code_hash
        identity = {"files": self.file_hashes, "engine": ENGINE_VERSION, "implementation": code_hash, "policy": POLICY.as_dict(), "schema": 1}
        self.version = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.catalog_version = "catalog-" + self.file_hashes["pricing_catalog.csv"][:12]
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"assumptions.json: duplicate field {key}")
                result[key] = value
            return result
        self.assumptions = json.loads((path / "assumptions.json").read_text(), object_pairs_hook=unique_keys)
        required = {"currency", "synthetic_data", "metrics", "resource_counts", "billing_history", "dataset_name", "pricing_source", "pricing_snapshot_date"}
        if not isinstance(self.assumptions, dict) or not required <= self.assumptions.keys():
            raise ValueError("assumptions.json: missing required manifest fields")
        if not isinstance(self.assumptions["metrics"], dict) or not {"start", "end_exclusive", "interval_minutes", "points_per_vm", "vm_count", "metric_rows", "gpu_metric_rows", "duration_days"} <= self.assumptions["metrics"].keys():
            raise ValueError("assumptions.json: missing required telemetry fields")
        if not isinstance(self.assumptions["resource_counts"], dict) or not isinstance(self.assumptions["billing_history"], dict):
            raise ValueError("assumptions.json: counts and billing history must be objects")
        months = self.assumptions["billing_history"].get("months")
        if type(months) is not int or months < 1:
            raise ValueError("assumptions.json: billing history months must be a positive integer")
        if self.assumptions.get("currency") != "INR" or self.assumptions.get("synthetic_data") is not True:
            raise ValueError("This adapter requires the declared synthetic INR benchmark contract")
        metrics = self.assumptions["metrics"]
        self.start = timestamp(metrics["start"])
        self.end = timestamp(metrics["end_exclusive"])
        def integer(value, name):
            if type(value) is not int or value < 0:
                raise ValueError(f"assumptions.json: {name} must be a nonnegative integer")
            return value
        self.interval = integer(metrics["interval_minutes"], "interval_minutes")
        seconds = (self.end - self.start).total_seconds()
        if not 5 <= self.interval <= 15 or seconds <= 0 or seconds % (self.interval * 60):
            raise ValueError("assumptions.json: invalid observation window/interval")
        points = int(seconds / (self.interval * 60))
        counts = self.assumptions["resource_counts"]
        if set(counts) != {"total", "vm", "block_volume", "public_ip", "gpu"}:
            raise ValueError("assumptions.json: resource_counts must describe every supported type")
        for kind, count in counts.items():
            integer(count, "resource_counts." + kind)
        if counts["total"] != sum(value for key, value in counts.items() if key != "total"):
            raise ValueError("assumptions.json: resource counts do not sum to total")
        expected = {"points_per_vm": points, "vm_count": counts["vm"],
                    "metric_rows": points * counts["vm"], "gpu_metric_rows": points * counts["gpu"]}
        for key, count in expected.items():
            if integer(metrics[key], key) != count:
                raise ValueError(f"assumptions.json: {key} disagrees with observation grid and resource counts")
        duration = integer(metrics["duration_days"], "duration_days")
        if seconds != duration * 86400 or duration < 30:
            raise ValueError("assumptions.json: declare at least 30 complete days of telemetry")

    def assert_unchanged(self):
        for name, expected in self.file_hashes.items():
            with (self.path / name).open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise ValueError(f"{name}: source changed during import; retry with a stable dataset")

    def load_catalog(self) -> list[ProviderPlan]:
        rows = list(records(self.path / "pricing_catalog.csv", {
            "plan_key", "hardware", "instance_family", "instance_type", "vcpu", "ram_gb",
            "disk_gb", "storage_type", "transfer_allowance_gb", "hourly_cost_inr",
            "quarterly_cost_inr", "pricing_source", "region_verified",
        }))
        unique(rows, "plan_key", "pricing_catalog.csv")
        plans = []
        for row in rows:
            quarterly = amount(row["quarterly_cost_inr"])
            hourly = amount(row["hourly_cost_inr"])
            if quarterly is None or hourly is None:
                raise ValueError(f"Missing compute tariff for {row['plan_key']}")
            plans.append(ProviderPlan(
                id=row["plan_key"], name=row["instance_type"], hardware=row["hardware"],
                instance_family=row["instance_family"], vcpu=int(row["vcpu"]),
                memory_gib=number(row["ram_gb"]), disk_gb=number(row["disk_gb"]),
                storage_type=row["storage_type"], transfer_allowance_gb=number(row["transfer_allowance_gb"]),
                compute_hourly_rate=hourly, compute_quarterly_rate=quarterly,
                compute_monthly_equivalent=monthly_equivalent(quarterly),
                pricing_source=row["pricing_source"], catalog_version=self.catalog_version,
                # A CSV claim alone is not independent provider verification.
                region_verified=False, pricing_verified=False,
            ))
        return plans

    def load_resources(self, plans: list[ProviderPlan]) -> list[Resource]:
        rows = list(records(self.path / "resources.csv", {
            "resource_id", "resource_type", "name", "region", "environment", "owner", "team",
            "status", "hardware", "instance_family", "plan_key", "vcpu", "ram_gb", "disk_gb",
            "storage_type", "transfer_allowance_gb", "criticality", "created_at", "attached_to",
            "lifecycle_state", "gpu_model", "gpu_vram_gb", "gpu_workload",
        }))
        indexed = unique(rows, "resource_id", "resources.csv")
        prices = unique(list(records(self.path / "pricing.csv", {
            "resource_id", "resource_type", "plan_key", "monthly_equivalent_inr", "monthly_equivalent_basis",
        })), "resource_id", "pricing.csv")
        if set(indexed) != set(prices):
            raise ValueError("Inventory and resource pricing IDs do not match")
        catalog = {plan.id: plan for plan in plans}
        resources = []
        for row in rows:
            price = prices[row["resource_id"]]
            resource = Resource(
                id=row["resource_id"], name=row["name"], type=row["resource_type"], region=row["region"],
                environment=row["environment"], team=row["team"] or None, owner=row["owner"] or None,
                current_plan_id=row["plan_key"] or None, dataset_version=self.version, status=row["status"],
                hardware=row["hardware"] or None, instance_family=row["instance_family"] or None,
                vcpu=int(row["vcpu"]) if row["vcpu"] else None, memory_gib=number(row["ram_gb"]),
                disk_gb=number(row["disk_gb"]), storage_type=row["storage_type"] or None,
                transfer_allowance_gb=number(row["transfer_allowance_gb"]), criticality=row["criticality"],
                created_at=timestamp(row["created_at"]), attached_to=row["attached_to"] or None,
                lifecycle_state=row["lifecycle_state"], gpu_model=row["gpu_model"] or None,
                gpu_vram_gib=number(row["gpu_vram_gb"]), gpu_workload=row["gpu_workload"] or None,
                monthly_cost=money(amount(price["monthly_equivalent_inr"])) if price["monthly_equivalent_inr"].strip() else None, cost_basis=price["monthly_equivalent_basis"] or None,
            )
            if price["resource_type"] != resource.type or price["plan_key"] != (resource.current_plan_id or ""):
                raise ValueError(f"Pricing identity mismatch for {resource.id}")
            if resource.type == "vm":
                plan = catalog.get(resource.current_plan_id)
                if not plan or (resource.vcpu, resource.memory_gib, resource.hardware, resource.instance_family, resource.disk_gb, resource.storage_type, resource.transfer_allowance_gb) != (
                    plan.vcpu, plan.memory_gib, plan.hardware, plan.instance_family, plan.disk_gb, plan.storage_type, plan.transfer_allowance_gb,
                ) or resource.monthly_cost != plan.compute_monthly_equivalent:
                    raise ValueError(f"Inventory/catalog/price inconsistency for {resource.id}")
            resources.append(resource)
        if len(resources) != self.assumptions["resource_counts"]["total"]:
            raise ValueError("Resource count disagrees with manifest")
        for kind, count in self.assumptions["resource_counts"].items():
            if kind != "total" and sum(resource.type == kind for resource in resources) != count:
                raise ValueError(f"Resource count disagrees with manifest for {kind}")
        by_id = {resource.id: resource for resource in resources}
        states = {"vm": {"running", "stopped"}, "block_volume": {"in_use", "available"},
                  "public_ip": {"associated", "reserved"}, "gpu": {"attached", "available"}}
        for resource in resources:
            if resource.status not in states[resource.type]:
                raise ValueError(f"resources.csv: unsupported status for {resource.id}")
            attached_state = resource.status in {"in_use", "associated", "attached"}
            if resource.type != "vm" and attached_state != bool(resource.attached_to):
                raise ValueError(f"resources.csv: status contradicts attachment for {resource.id}")
            expected_lifecycle = "active" if resource.type == "vm" or resource.attached_to else "unassociated" if resource.type == "public_ip" else "unattached"
            if resource.lifecycle_state != expected_lifecycle:
                raise ValueError(f"resources.csv: lifecycle contradicts attachment for {resource.id}")
            if resource.attached_to:
                host = by_id.get(resource.attached_to)
                if host is None or host.type != "vm" or resource.type == "vm":
                    raise ValueError(f"resources.csv: attachment for {resource.id} must reference a VM host")
                if resource.lifecycle_state in {"unattached", "unassociated"}:
                    raise ValueError(f"resources.csv: orphan lifecycle contradicts attachment for {resource.id}")
        return resources

    def metric_rows(self, vm_ids: set[str]):
        for row in records(self.path / "metrics.csv", {"timestamp", "resource_id", "quality_flag", *CSV_METRICS.values()}):
            if row["resource_id"] not in vm_ids:
                raise ValueError(f"Telemetry references unknown VM {row['resource_id']}")
            when = timestamp(row["timestamp"])
            if not self.start <= when < self.end or (when - self.start).total_seconds() % (self.interval * 60):
                raise ValueError("VM telemetry contains an off-grid/out-of-window timestamp")
            flag = row["quality_flag"]
            reported_invalid = flag == "invalid_observation"
            values = []
            for metric, column in CSV_METRICS.items():
                try:
                    value = number(row[column])
                    if value is not None and (value < 0 or (metric in {"cpu", "memory", "disk"} and value > 100)):
                        raise ValueError("Invalid metric range")
                except ValueError:
                    value, flag = None, "invalid_observation"
                values.append(value)
            if reported_invalid:
                values = [None] * len(values)
            if flag == "missing_observation":
                if any(value is not None for value in values):
                    raise ValueError("Missing-observation row contains metric values")
            elif flag not in {"observed_synthetic", "invalid_observation"}:
                raise ValueError(f"Unknown telemetry quality flag {flag}")
            yield (row["resource_id"], when.isoformat(), *values, flag)

    def gpu_rows(self, gpu_capacities: dict[str, float | None]):
        columns = ("gpu_utilization_pct", "gpu_memory_utilization_pct", "gpu_memory_used_gb", "gpu_power_w")
        for row in records(self.path / "gpu_metrics.csv", {"timestamp", "resource_id", *columns}):
            if row["resource_id"] not in gpu_capacities:
                raise ValueError("GPU telemetry references unknown accelerator")
            when = timestamp(row["timestamp"])
            if not self.start <= when < self.end or (when - self.start).total_seconds() % (self.interval * 60):
                raise ValueError("GPU telemetry contains an off-grid/out-of-window timestamp")
            values = [number(row[column]) for column in columns]
            if any(value is not None and (value < 0 or (index < 2 and value > 100)) for index, value in enumerate(values)):
                raise ValueError("GPU telemetry contains invalid values")
            capacity = gpu_capacities[row["resource_id"]]
            if capacity is not None and values[2] is not None and values[2] > capacity:
                raise ValueError("GPU memory usage exceeds the declared accelerator capacity")
            yield (row["resource_id"], when.isoformat(), *values)

    def load_relationships(self, resources: list[Resource]) -> list[dict]:
        by_id = {resource.id: resource for resource in resources}
        rows = self.related_rows("resource_relationships.csv", {"source_resource_id", "target_resource_id"}, set(by_id), {"relationship_type", "evidence"})
        types = {"attached_volume": "block_volume", "associated_public_ip": "public_ip", "attached_gpu": "gpu"}
        attached = set()
        for row in rows:
            host, child = by_id[row["source_resource_id"]], by_id[row["target_resource_id"]]
            if host.type != "vm" or child.type != types.get(row["relationship_type"]) or child.attached_to != host.id:
                raise ValueError("resource_relationships.csv: relationship contradicts inventory type or attachment")
            if child.id in attached:
                raise ValueError("resource_relationships.csv: duplicate or conflicting attachment")
            attached.add(child.id)
        if attached != {resource.id for resource in resources if resource.attached_to}:
            raise ValueError("resource_relationships.csv: inventory attachment is missing from relationships")
        return rows

    def event_rows(self, resource_ids: set[str]) -> list[dict]:
        rows = self.related_rows("events.csv", {"resource_id"}, resource_ids, {"event_id", "event_type", "start_time", "end_time", "severity", "description", "synthetic"})
        for row in rows:
            if not row["event_id"].strip() or row["synthetic"].lower() != "true":
                raise ValueError("events.csv: expected an identified synthetic event")
            if row["severity"] not in {"info", "low", "medium", "high", "warning", "critical"}:
                raise ValueError("events.csv: unknown severity")
            start = timestamp(row["start_time"])
            end = timestamp(row["end_time"]) if row["end_time"] else None
            if end is not None and end < start:
                raise ValueError("events.csv: event end precedes its start")
            row["start_time"] = start.isoformat()
            row["end_time"] = end.isoformat() if end else ""
        return rows

    def related_rows(self, filename: str, id_columns: set[str], resource_ids: set[str], required: set[str] | None = None) -> list[dict]:
        rows = list(records(self.path / filename, id_columns | (required or set())))
        for row in rows:
            if any(row[column] not in resource_ids for column in id_columns):
                raise ValueError(f"{filename} references an unknown resource")
        return rows
