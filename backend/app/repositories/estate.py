import json
import sqlite3
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from app.adapters.dataset import ASSUMPTIONS, DatasetSource, amount, records
from app.database import connect, initialize
from app.engine.alerts import resource_alerts
from app.engine.costs import money
from app.engine.optimizer import optimize
from app.engine.policy import ENGINE_VERSION, POLICY
from app.engine.statistics import analyze
from app.models.contracts import Analysis, Provenance, RecommendationSummary


def bulk_insert(connection: sqlite3.Connection, statement: str, rows) -> int:
    iterator = iter(rows)
    count = 0
    while batch := list(islice(iterator, 10_000)):
        connection.executemany(statement, batch)
        count += len(batch)
    return count


def import_dataset(database_path: Path, dataset_path: Path) -> dict:
    """One atomic, versioned import; a failed import cannot publish partial data."""
    initialize(database_path)
    source = DatasetSource(dataset_path)
    with connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute("SELECT payload FROM metadata WHERE key='dataset'").fetchone()
        if existing and json.loads(existing["payload"])["version"] == source.version:
            return json.loads(existing["payload"])
        # Decisions/audit are retained under snapshot-specific recommendation IDs.
        for table in ("metrics", "gpu_metrics", "analyses", "recommendations", "events", "billing", "alerts", "relationships", "resources", "plans"):
            connection.execute(f"DELETE FROM {table}")
        plans = source.load_catalog()
        resources = source.load_resources(plans)
        resource_ids = {resource.id for resource in resources}
        connection.executemany("INSERT INTO resources VALUES (?,?)", [(resource.id, resource.model_dump_json()) for resource in resources])
        connection.executemany("INSERT INTO plans VALUES (?,?)", [(plan.id, plan.model_dump_json()) for plan in plans])
        try:
            metric_count = bulk_insert(connection, "INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?)",
                                       source.metric_rows({resource.id for resource in resources if resource.type == "vm"}))
            gpu_count = bulk_insert(connection, "INSERT INTO gpu_metrics VALUES (?,?,?,?,?,?)",
                                    source.gpu_rows({resource.id for resource in resources if resource.type == "gpu"}))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Duplicate metric timestamp/resource pair in source data") from exc
        if metric_count != source.assumptions["metrics"]["metric_rows"] or gpu_count != source.assumptions["metrics"]["gpu_metric_rows"]:
            raise ValueError("Telemetry row counts disagree with the delivered manifest")
        relationships = source.related_rows("resource_relationships.csv", {"source_resource_id", "target_resource_id"}, resource_ids)
        connection.executemany("INSERT INTO relationships VALUES (?)", [(json.dumps(row),) for row in relationships])
        event_rows = source.related_rows("events.csv", {"resource_id"}, resource_ids)
        event_index = {}
        for row in event_rows:
            if not row["event_id"]:
                raise ValueError("events.csv contains an empty event ID")
            if row["event_id"] in event_index and event_index[row["event_id"]] != row:
                raise ValueError("events.csv contains conflicting records with the same event ID")
            event_index[row["event_id"]] = row
        events = list(event_index.values())
        connection.executemany("INSERT INTO events VALUES (?,?,?)", [(row["event_id"], row["resource_id"], json.dumps(row)) for row in events])
        billing = list(records(dataset_path / "billing_history.csv", {"billing_month", "resource_id", "synthetic_billed_amount_inr", "synthetic"}))
        billing_rows = []
        for row in billing:
            if row["resource_id"] not in resource_ids or row["synthetic"].lower() != "true":
                raise ValueError("Invalid synthetic billing reference")
            datetime.strptime(row["billing_month"], "%Y-%m")
            billed = amount(row["synthetic_billed_amount_inr"])
            if billed is None:
                raise ValueError("Missing synthetic billed amount")
            billing_rows.append((row["billing_month"], row["resource_id"], str(money(billed))))
        connection.executemany("INSERT INTO billing VALUES (?,?,?)", billing_rows)
        provenance = Provenance(
            dataset_version=source.version, catalog_version=source.catalog_version,
            policy_version=POLICY.version, engine_version=f"{ENGINE_VERSION}+{source.implementation_hash[:8]}", analysis_as_of=source.end,
            pricing_source=source.assumptions["pricing_source"], assumptions=ASSUMPTIONS,
        )
        gpu_hosts = {row["source_resource_id"] for row in relationships if row["relationship_type"] == "attached_gpu"}
        recommendation_count = alert_count = 0
        for resource in resources:
            rows = [dict(row) for row in connection.execute("SELECT * FROM metrics WHERE resource_id=? ORDER BY timestamp", (resource.id,))] if resource.type == "vm" else []
            analysis = analyze(resource.id, rows, source.start, source.end, source.interval, vcpu=resource.vcpu, memory_gib=resource.memory_gib) if resource.type == "vm" else None
            if analysis:
                connection.execute("INSERT INTO analyses VALUES (?,?)", (resource.id, analysis.model_dump_json()))
                resource.cpu_p95 = analysis.statistics["cpu"].p95 if "cpu" in analysis.statistics else None
                resource.memory_p95 = analysis.statistics["memory"].p95 if "memory" in analysis.statistics else None
                resource.coverage = analysis.quality.coverage
                connection.execute("UPDATE resources SET payload=? WHERE id=?", (resource.model_dump_json(), resource.id))
                for alert in resource_alerts(resource, analysis, rows):
                    connection.execute("INSERT INTO alerts VALUES (?,?)", (alert.id, alert.model_dump_json()))
                    alert_count += 1
            for recommendation in optimize(resource, plans, analysis, rows, provenance, resource.id in gpu_hosts):
                summary = RecommendationSummary.model_validate({key: getattr(recommendation, key) for key in RecommendationSummary.model_fields})
                connection.execute("INSERT INTO recommendations VALUES (?,?,?,?)", (recommendation.id, resource.id, recommendation.model_dump_json(), summary.model_dump_json()))
                recommendation_count += 1
        metadata = {
            "version": source.version, "catalog_version": source.catalog_version, "engine_version": ENGINE_VERSION,
            "implementation_hash": source.implementation_hash,
            "name": source.assumptions["dataset_name"], "synthetic": True,
            "mode": "historical_synthetic_snapshot", "timestamp_assumption": "UTC (unverified source timezone)",
            "analysis_as_of": source.end.isoformat(), "window_start": source.start.isoformat(),
            "interval_minutes": source.interval, "duration_days": (source.end - source.start).days,
            "resource_count": len(resources), "resource_counts": source.assumptions["resource_counts"],
            "metric_rows": metric_count, "gpu_metric_rows": gpu_count, "catalog_count": len(plans),
            "billing_rows": len(billing_rows), "recommendation_count": recommendation_count, "alert_count": alert_count,
            "event_source_rows": len(event_rows), "event_count": len(events), "duplicate_event_rows": len(event_rows) - len(events),
            "unknown_price_count": sum(resource.monthly_cost is None for resource in resources),
            "missing_observation_rows": connection.execute("SELECT COUNT(*) FROM metrics WHERE quality_flag='missing_observation'").fetchone()[0],
            "invalid_observation_rows": connection.execute("SELECT COUNT(*) FROM metrics WHERE quality_flag='invalid_observation'").fetchone()[0],
            "imported_at": datetime.now(timezone.utc).isoformat(), "file_hashes": source.file_hashes,
            "policy": POLICY.as_dict(), "assumptions": ASSUMPTIONS,
            "pricing_source": source.assumptions["pricing_source"],
            "pricing_snapshot_date": source.assumptions["pricing_snapshot_date"],
            "cost_basis": "Quarterly compute total / 3 plus block storage per month; GST/discounts excluded.",
            "verified_savings": None, "budget": None,
        }
        connection.execute("INSERT OR REPLACE INTO metadata VALUES ('dataset',?)", (json.dumps(metadata),))
        return metadata


def read_analysis(connection: sqlite3.Connection, resource_id: str) -> Analysis | None:
    row = connection.execute("SELECT payload FROM analyses WHERE resource_id=?", (resource_id,)).fetchone()
    return Analysis.model_validate_json(row["payload"]) if row else None
