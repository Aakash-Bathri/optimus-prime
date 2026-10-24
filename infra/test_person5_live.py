"""Explicit live acceptance: changes tagged LocalStack fixtures and optionally opens a real test PR."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import dotenv_values
from fastapi.testclient import TestClient

from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["llm", "scripted"], default="scripted")
    parser.add_argument("--create-pr", action="store_true", help="Open a real PR in the configured demo repo")
    args = parser.parse_args()
    config = dotenv_values(ROOT / ".env")
    if config.get("CLOUDPILOT_GITHUB_TEST_REPO") != "Harshavardhan2903/cloudpilot-terraform-demo":
        raise RuntimeError("Live harness is restricted to the dedicated test repository")
    report = {"passed": False, "mode": args.mode, "checks": {}, "pr_url": None}
    target = ROOT / "data/local/person5-live.json"

    try:
        with TestClient(create_app()) as client:
            client.headers["Authorization"] = "Bearer " + config["CLOUDPILOT_EXECUTION_TOKEN"]

            def request(method, path, body=None, status=200):
                response = client.request(method, "/api/execution" + path,
                    **({"json": body} if body is not None else {}))
                if response.status_code != status:
                    raise RuntimeError(f"{path}: expected HTTP {status}, received {response.status_code}: {response.text[:1000]}")
                return response.json()

            def prepare(resource_id, mode):
                recommendation = request("GET", "/demo/recommendation/" + resource_id)
                return request("POST", "/proposals", {"recommendation": recommendation, "mode": mode})

            def approve_execute(proposal):
                request("POST", f"/proposals/{proposal['id']}/decision", {
                    "digest": proposal["digest"], "decision": "approve"})
                return request("POST", f"/proposals/{proposal['id']}/execute", {"digest": proposal["digest"]})

            print("Registering live demo mappings", flush=True)
            request("POST", "/demo/setup")
            before = request("GET", "/resources")
            manual = next(item for item in before if item["management"] == "manual")
            if manual["current"]["instance_type"] != "m5.2xlarge" or manual["current"]["state"] != "running":
                raise RuntimeError("Manual fixture must start running at m5.2xlarge; inspect and restore it first")

            print("Checking rejection blocks a live LocalStack mutation", flush=True)
            rejected = prepare("demo-manual-01", "scripted")
            request("POST", f"/proposals/{rejected['id']}/execute", {"digest": rejected["digest"]}, status=409)
            request("POST", f"/proposals/{rejected['id']}/decision", {"digest": rejected["digest"], "decision": "reject"})
            request("POST", f"/proposals/{rejected['id']}/execute", {"digest": rejected["digest"]}, status=409)
            assert before == request("GET", "/resources")
            report["checks"]["rejection_prevents_mutation"] = True

            print("Preparing and executing a live manual resize", flush=True)
            proposal = prepare("demo-manual-01", args.mode)
            applied = approve_execute(proposal)
            assert applied["status"] == "APPLIED"
            assert applied["result"]["after"]["instance_type"] == "m5.xlarge"
            assert applied["result"]["after"]["state"] == "running"
            assert request("POST", f"/proposals/{proposal['id']}/execute", {"digest": proposal["digest"]}) == applied
            report["checks"]["manual_resize_verified"] = True
            report["checks"]["manual_duplicate_execution_is_idempotent"] = True

            print("Approving a fresh inverse preview and verifying restore", flush=True)
            inverse = request("POST", f"/proposals/{proposal['id']}/rollback?mode=scripted")
            restored = approve_execute(inverse)
            assert restored["status"] == "APPLIED"
            assert restored["result"]["after"] == manual["current"]
            report["checks"]["approved_restore_verified"] = True

            if args.create_pr:
                print("Preparing and validating the real Terraform PR", flush=True)
                terraform_before = next(item for item in request("GET", "/resources") if item["management"] == "terraform")["current"]
                rejected_tf = prepare("demo-api-01", "scripted")
                request("POST", f"/proposals/{rejected_tf['id']}/decision", {"digest": rejected_tf["digest"], "decision": "reject"})
                request("POST", f"/proposals/{rejected_tf['id']}/execute", {"digest": rejected_tf["digest"]}, status=409)
                proposal = prepare("demo-api-01", args.mode)
                created = approve_execute(proposal)
                assert created["status"] == "PR_CREATED"
                assert request("POST", f"/proposals/{proposal['id']}/execute", {"digest": proposal["digest"]}) == created
                terraform_after = next(item for item in request("GET", "/resources") if item["management"] == "terraform")["current"]
                assert terraform_before == terraform_after
                report["pr_url"] = created["result"]["url"]
                report["checks"].update(terraform_fmt_and_validate=True, terraform_pr_created=True,
                    terraform_duplicate_execution_is_idempotent=True, terraform_infrastructure_unchanged=True)
            report["checks"]["audit_persisted"] = bool(request("GET", "/audit"))
            report["passed"] = all(report["checks"].values())
    finally:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
