"""Persistent proposals, exact approvals, resource leases and append-only audit."""

import json
from uuid import uuid4

from app.database import connect
from app.execution.contracts import WorkflowError, utcnow


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with connect(path) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS execution_bindings (
                    resource_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_proposals (
                    id TEXT PRIMARY KEY, resource_id TEXT NOT NULL, status TEXT NOT NULL,
                    body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_leases (
                    resource_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS execution_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT,
                    timestamp TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL);
            """)

    def bindings(self):
        with connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT body FROM execution_bindings ORDER BY resource_id")]

    def bind(self, binding):
        body = binding.model_dump(mode="json")
        with connect(self.path) as db:
            # A remapping is deliberate; prepared approvals will fail their binding hash check.
            db.execute("INSERT INTO execution_bindings VALUES (?,?) ON CONFLICT(resource_id) "
                       "DO UPDATE SET body=excluded.body", (binding.resource_id, json.dumps(body)))
        self.audit(None, "resource_registered", {"binding": body})
        return body

    def binding(self, resource_id):
        return next((item for item in self.bindings() if item["resource_id"] == resource_id), None)

    def create(self, body):
        body = {**body, "id": str(uuid4()), "status": "AWAITING_APPROVAL",
                "created_at": utcnow().isoformat()}
        with connect(self.path) as db:
            db.execute("INSERT INTO execution_proposals VALUES (?,?,?,?)",
                       (body["id"], body["binding"]["resource_id"], body["status"], json.dumps(body)))
        self.audit(body["id"], "proposal_prepared", {"digest": body["digest"]})
        return body

    def get(self, identifier):
        with connect(self.path) as db:
            row = db.execute("SELECT body FROM execution_proposals WHERE id=?", (identifier,)).fetchone()
        if not row:
            raise WorkflowError("Proposal not found", 404)
        return json.loads(row[0])

    def proposals(self):
        with connect(self.path) as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT body FROM execution_proposals ORDER BY rowid DESC LIMIT 100")]

    def transition(self, identifier, expected, status, **updates):
        with connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status, body FROM execution_proposals WHERE id=?", (identifier,)).fetchone()
            if not row or row[0] not in expected:
                raise WorkflowError("Proposal state changed; refresh before continuing")
            body = {**json.loads(row[1]), **updates, "status": status}
            db.execute("UPDATE execution_proposals SET status=?,body=? WHERE id=?",
                       (status, json.dumps(body), identifier))
        self.audit(identifier, status.lower(), {"status": status})
        return body

    def claim(self, identifier, digest):
        with connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM execution_proposals WHERE id=?", (identifier,)).fetchone()
            if not row:
                raise WorkflowError("Proposal not found", 404)
            body = json.loads(row[0])
            if body["digest"] != digest:
                raise WorkflowError("Approval digest does not match the preview")
            if body["status"] in ("APPLIED", "PR_CREATED"):
                return body, False
            if body["status"] != "APPROVED":
                raise WorkflowError("An exact approved proposal is required")
            resource_id = body["binding"]["resource_id"]
            if db.execute("SELECT 1 FROM execution_leases WHERE resource_id=?", (resource_id,)).fetchone():
                raise WorkflowError("Another execution owns this resource; inspect its status")
            db.execute("INSERT INTO execution_leases VALUES (?,?)", (resource_id, identifier))
            body["status"] = "EXECUTING"
            db.execute("UPDATE execution_proposals SET status=?,body=? WHERE id=?",
                       (body["status"], json.dumps(body), identifier))
        self.audit(identifier, "execution_started", {"digest": digest})
        return body, True

    def release(self, identifier):
        with connect(self.path) as db:
            db.execute("DELETE FROM execution_leases WHERE proposal_id=?", (identifier,))

    def recover_interrupted(self):
        # Call once when the single local API worker starts, never per request.
        with connect(self.path) as db:
            rows = db.execute("SELECT id,body FROM execution_proposals WHERE status='EXECUTING'").fetchall()
            for row in rows:
                body = json.loads(row["body"])
                body.update(status="RECOVERY_REQUIRED", error="API stopped during execution. Inspect live state before continuing.")
                db.execute("UPDATE execution_proposals SET status=?,body=? WHERE id=?",
                           (body["status"], json.dumps(body), row["id"]))

    def audit(self, identifier, event, details):
        with connect(self.path) as db:
            db.execute("INSERT INTO execution_audit(proposal_id,timestamp,event,details) VALUES (?,?,?,?)",
                       (identifier, utcnow().isoformat(), event, json.dumps(details)))

    def history(self, identifier=None):
        with connect(self.path) as db:
            rows = db.execute("SELECT * FROM execution_audit WHERE (? IS NULL OR proposal_id=?) "
                              "ORDER BY sequence DESC LIMIT 200", (identifier, identifier)).fetchall()
        return [{**dict(row), "details": json.loads(row["details"])} for row in rows]
