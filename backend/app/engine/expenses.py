"""Reconciled expense views over the imported, monthly synthetic billing."""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from app.database import connect
from app.engine.costs import money

SOURCE_ID = "utho-benchmark"
SOURCE_NAME = "Utho benchmark"
ORGANIZATION = {"id": "cloudpilot-local", "name": "CloudPilot demo"}


def billing_range(database_path):
    with connect(database_path) as connection:
        row = connection.execute("SELECT MIN(month) AS first, MAX(month) AS last FROM billing").fetchone()
    first = date.fromisoformat(row["first"] + "-01")
    last_month = date.fromisoformat(row["last"] + "-01")
    return first, last_month.replace(day=monthrange(last_month.year, last_month.month)[1])


def expenses(database_path, resources, *, start=None, end=None, granularity="day", breakdown="data_source"):
    available_start, available_end = billing_range(database_path)
    start = start or available_end.replace(day=1)
    end = end or available_end
    if start > end:
        raise ValueError("Start date must be on or before end date")
    if start < available_start or end > available_end:
        raise ValueError(f"Billing data is available from {available_start} to {available_end}")
    if (end - start).days > 366:
        raise ValueError("Choose a period of at most 367 days")

    indexed = {resource.id: resource for resource in resources}
    amounts = {resource.id: None for resource in resources}
    groups = {}
    points = {}

    def bucket(day):
        if granularity == "month":
            return day.replace(day=1)
        if granularity == "week":
            return day - timedelta(days=day.weekday())
        return day

    day = start
    while day <= end:
        key = bucket(day).isoformat()
        point = points.setdefault(key, {"start": day.isoformat(), "end": day.isoformat(), "amount": Decimal(0), "groups": {}})
        point["end"] = day.isoformat()
        day += timedelta(days=1)

    for resource in resources:
        key = SOURCE_ID if breakdown == "data_source" else getattr(resource, "type" if breakdown == "resource_type" else breakdown) or "Unassigned"
        group = groups.setdefault(key, {"id": key, "name": SOURCE_NAME if breakdown == "data_source" else key, "amount": Decimal(0), "resource_ids": set(), "unknown_price_count": 0})
        group["resource_ids"].add(resource.id)

    with connect(database_path) as connection:
        rows = connection.execute("SELECT month, resource_id, amount FROM billing WHERE month >= ? AND month <= ? ORDER BY month, resource_id", (start.strftime("%Y-%m"), end.strftime("%Y-%m")))
        for row in rows:
            resource = indexed.get(row["resource_id"])
            if resource is None:
                continue
            month = date.fromisoformat(row["month"] + "-01")
            days = monthrange(month.year, month.month)[1]
            # Allocate integer paise, with the remainder assigned to the first days.
            # Every daily/weekly partition therefore adds to the original month.
            quotient, remainder = divmod(int(Decimal(row["amount"]) * 100), days)
            first_day = max(start, month)
            last_day = min(end, month.replace(day=days))
            key = SOURCE_ID if breakdown == "data_source" else getattr(resource, "type" if breakdown == "resource_type" else breakdown) or "Unassigned"
            day = first_day
            while day <= last_day:
                amount = Decimal(quotient + int(day.day <= remainder)) / 100
                point = points[bucket(day).isoformat()]
                point["amount"] += amount
                point["groups"][key] = point["groups"].get(key, Decimal(0)) + amount
                groups[key]["amount"] += amount
                amounts[resource.id] = (amounts[resource.id] or Decimal(0)) + amount
                day += timedelta(days=1)

    for resource in resources:
        if amounts[resource.id] is None:
            key = SOURCE_ID if breakdown == "data_source" else getattr(resource, "type" if breakdown == "resource_type" else breakdown) or "Unassigned"
            groups[key]["unknown_price_count"] += 1

    return {
        "start": start.isoformat(), "end": end.isoformat(),
        "available_start": available_start.isoformat(), "available_end": available_end.isoformat(),
        "granularity": granularity, "breakdown": breakdown, "currency": "INR", "synthetic": True,
        "total": str(money(sum((amount for amount in amounts.values() if amount is not None), Decimal(0)))),
        "resource_count": len(resources), "unknown_price_count": sum(amount is None for amount in amounts.values()),
        "allocation_note": "Synthetic monthly billing. Daily and weekly expenses are even allocations in paise, not measured daily charges. Unpriced resources are excluded from totals.",
        "points": [{**point, "amount": str(money(point["amount"])), "groups": {key: str(money(amount)) for key, amount in point["groups"].items()}} for point in points.values()],
        "groups": [{"id": group["id"], "name": group["name"], "amount": str(money(group["amount"])), "resource_count": len(group["resource_ids"]), "unknown_price_count": group["unknown_price_count"]} for group in sorted(groups.values(), key=lambda item: -item["amount"])],
        "resources": [{"resource_id": resource_id, "amount": str(money(amount)) if amount is not None else None} for resource_id, amount in sorted(amounts.items(), key=lambda item: -(item[1] or Decimal(0)))],
    }


def data_sources(database_path, metadata, resources):
    start, end = billing_range(database_path)
    return {
        "organization": ORGANIZATION,
        "items": [{
            "id": SOURCE_ID, "name": SOURCE_NAME, "provider": "Utho", "kind": "Local dataset",
            "resource_count": len(resources), "unknown_price_count": sum(resource.monthly_cost is None for resource in resources),
            "imported_at": metadata["imported_at"], "billing_start": start.isoformat(), "billing_end": end.isoformat(),
            "classifications": [{"type": kind, "count": sum(resource.type == kind for resource in resources)} for kind in ("vm", "block_volume", "public_ip", "gpu")],
            "feeds": [
                {"name": "Resource inventory", "file": "resources.csv", "rows": len(resources), "classification": "All resource types"},
                {"name": "VM telemetry", "file": "metrics.csv", "rows": metadata["metric_rows"], "classification": "Virtual machines"},
                {"name": "GPU telemetry", "file": "gpu_metrics.csv", "rows": metadata["gpu_metric_rows"], "classification": "GPUs"},
                {"name": "Billing history", "file": "billing_history.csv", "rows": metadata["billing_rows"], "classification": "Priced resources"},
                {"name": "Pricing catalog", "file": "pricing_catalog.csv", "rows": metadata["catalog_count"], "classification": "Compute configurations"},
            ],
        }],
    }
