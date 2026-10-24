"""Read only the delivered source contracts; outcome labels are never inputs."""

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.engine.costs import money, monthly_equivalent
from app.engine.policy import ENGINE_VERSION, POLICY
from app.models.contracts import ProviderPlan, Resource

SOURCE_FILES = (
    "assumptions.json", "resources.csv", "pricing_catalog.csv", "pricing.csv",
    "metrics.csv", "gpu_metrics.csv", "resource_relationships.csv", "events.csv",
    "billing_history.csv", "data_quality_summary.json",
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
    result = Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid monetary source value")
    return result


def records(path: Path, required: set[str]):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"{path.name}: missing columns {sorted(required - set(reader.fieldnames or []))}")
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name}:{line}: malformed CSV row")
            yield row


def unique(rows: list[dict], key: str, source: str) -> dict[str, dict]:
    indexed = {row[key]: row for row in rows}
    if len(indexed) != len(rows) or "" in indexed:
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
        code_files = sorted((app_root / "engine").glob("*.py")) + [Path(__file__), app_root / "models/contracts.py", app_root / "repositories/estate.py"]
        code_hash = hashlib.sha256(b"".join(file.read_bytes() for file in code_files)).hexdigest()
        self.implementation_hash = code_hash
        identity = {"files": self.file_hashes, "engine": ENGINE_VERSION, "implementation": code_hash, "policy": POLICY.as_dict(), "schema": 1}
        self.version = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        self.catalog_version = "catalog-" + self.file_hashes["pricing_catalog.csv"][:12]
        self.assumptions = json.loads((path / "assumptions.json").read_text())
        if self.assumptions.get("currency") != "INR" or self.assumptions.get("synthetic_data") is not True:
            raise ValueError("This adapter requires the declared synthetic INR benchmark contract")
        metrics = self.assumptions["metrics"]
        self.start = timestamp(metrics["start"])
        self.end = timestamp(metrics["end_exclusive"])
        self.interval = int(metrics["interval_minutes"])
        if self.interval <= 0 or self.end <= self.start:
            raise ValueError("Invalid observation window/interval")

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
                if not plan or (resource.vcpu, resource.memory_gib, resource.hardware, resource.instance_family, resource.disk_gb, resource.storage_type) != (
                    plan.vcpu, plan.memory_gib, plan.hardware, plan.instance_family, plan.disk_gb, plan.storage_type,
                ) or resource.monthly_cost != plan.compute_monthly_equivalent:
                    raise ValueError(f"Inventory/catalog/price inconsistency for {resource.id}")
            resources.append(resource)
        if len(resources) != self.assumptions["resource_counts"]["total"]:
            raise ValueError("Resource count disagrees with manifest")
        for kind, count in self.assumptions["resource_counts"].items():
            if kind != "total" and sum(resource.type == kind for resource in resources) != count:
                raise ValueError(f"Resource count disagrees with manifest for {kind}")
        for resource in resources:
            if resource.attached_to and resource.attached_to not in indexed:
                raise ValueError(f"Unknown attachment for {resource.id}")
        return resources

    def metric_rows(self, vm_ids: set[str]):
        for row in records(self.path / "metrics.csv", {"timestamp", "resource_id", "quality_flag", *CSV_METRICS.values()}):
            if row["resource_id"] not in vm_ids:
                raise ValueError(f"Telemetry references unknown VM {row['resource_id']}")
            when = timestamp(row["timestamp"])
            if not self.start <= when < self.end or (when - self.start).total_seconds() % (self.interval * 60):
                raise ValueError("VM telemetry contains an off-grid/out-of-window timestamp")
            flag = row["quality_flag"]
            values = []
            for metric, column in CSV_METRICS.items():
                try:
                    value = number(row[column])
                    if value is not None and (value < 0 or (metric in {"cpu", "memory", "disk"} and value > 100)):
                        raise ValueError("Invalid metric range")
                except ValueError:
                    value, flag = None, "invalid_observation"
                values.append(value)
            if flag == "missing_observation":
                if any(value is not None for value in values):
                    raise ValueError("Missing-observation row contains metric values")
            elif flag not in {"observed_synthetic", "invalid_observation"}:
                raise ValueError(f"Unknown telemetry quality flag {flag}")
            yield (row["resource_id"], when.isoformat(), *values, flag)

    def gpu_rows(self, gpu_ids: set[str]):
        columns = ("gpu_utilization_pct", "gpu_memory_utilization_pct", "gpu_memory_used_gb", "gpu_power_w")
        for row in records(self.path / "gpu_metrics.csv", {"timestamp", "resource_id", *columns}):
            if row["resource_id"] not in gpu_ids:
                raise ValueError("GPU telemetry references unknown accelerator")
            when = timestamp(row["timestamp"])
            if not self.start <= when < self.end or (when - self.start).total_seconds() % (self.interval * 60):
                raise ValueError("GPU telemetry contains an off-grid/out-of-window timestamp")
            values = [number(row[column]) for column in columns]
            if any(value is not None and (value < 0 or (index < 2 and value > 100)) for index, value in enumerate(values)):
                raise ValueError("GPU telemetry contains invalid values")
            yield (row["resource_id"], when.isoformat(), *values)

    def related_rows(self, filename: str, id_columns: set[str], resource_ids: set[str]) -> list[dict]:
        rows = list(records(self.path / filename, id_columns))
        for row in rows:
            if any(row[column] not in resource_ids for column in id_columns):
                raise ValueError(f"{filename} references an unknown resource")
        return rows
