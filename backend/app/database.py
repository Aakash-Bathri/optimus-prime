import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS resources (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS metrics (
                resource_id TEXT NOT NULL REFERENCES resources(id), timestamp TEXT NOT NULL,
                cpu REAL, memory REAL, disk REAL, iops REAL, network_in REAL, network_out REAL,
                quality_flag TEXT NOT NULL, PRIMARY KEY (resource_id, timestamp)
            );
            CREATE TABLE IF NOT EXISTS gpu_metrics (
                resource_id TEXT NOT NULL REFERENCES resources(id), timestamp TEXT NOT NULL,
                utilization REAL, memory_pct REAL, memory_gib REAL, power_w REAL,
                PRIMARY KEY (resource_id, timestamp)
            );
            CREATE TABLE IF NOT EXISTS analyses (resource_id TEXT PRIMARY KEY REFERENCES resources(id), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS recommendations (id TEXT PRIMARY KEY, resource_id TEXT NOT NULL REFERENCES resources(id), payload TEXT NOT NULL, summary TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS relationships (payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, resource_id TEXT NOT NULL REFERENCES resources(id), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS billing (month TEXT NOT NULL, resource_id TEXT NOT NULL REFERENCES resources(id), amount TEXT NOT NULL, PRIMARY KEY (month, resource_id));
            CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (recommendation_id TEXT PRIMARY KEY, decision TEXT NOT NULL CHECK(decision IN ('pending','accepted','rejected')), revision INTEGER NOT NULL, decided_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, recommendation_id TEXT NOT NULL, actor TEXT NOT NULL, previous_decision TEXT NOT NULL, decision TEXT NOT NULL, timestamp TEXT NOT NULL, version TEXT NOT NULL);
        """)
        if "summary" not in {row["name"] for row in connection.execute("PRAGMA table_info(recommendations)")}:
            connection.execute("ALTER TABLE recommendations ADD COLUMN summary TEXT NOT NULL DEFAULT ''")

