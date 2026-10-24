"""GitHub App installation auth and an idempotent, customer-applied PR path."""

import base64
import json
import time
from urllib.parse import quote

import httpx
import jwt

from app.config import ROOT
from app.execution.contracts import WorkflowError


class GitHub:
    def __init__(self, config):
        self.config = config

    def client(self, repository):
        allowed = self.config.get("CLOUDPILOT_GITHUB_TEST_REPO", "")
        if repository != allowed:
            raise WorkflowError("Repository is not the configured CloudPilot repository", 403)
        try:
            now = int(time.time())
            signed = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.config["GITHUB_APP_ID"]},
                (ROOT / self.config["GITHUB_APP_PRIVATE_KEY_PATH"]).read_bytes(), algorithm="RS256")
        except (KeyError, OSError):
            raise WorkflowError("GitHub App ID/private key is not configured", 503) from None
        with httpx.Client(base_url="https://api.github.com", timeout=30,
                          headers={"Authorization": "Bearer " + signed,
                                   "Accept": "application/vnd.github+json"}) as app:
            installation = self.request(app, "GET", f"/repos/{repository}/installation")
            token = self.request(app, "POST", f"/app/installations/{installation['id']}/access_tokens", json={
                "repositories": [repository.split("/")[1]],
                "permissions": {"contents": "write", "pull_requests": "write"},
            })["token"]
        return httpx.Client(base_url="https://api.github.com", timeout=30, headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        })

    @staticmethod
    def request(client, method, path, **kwargs):
        try:
            response = client.request(method, path, **kwargs)
        except httpx.RequestError:
            raise WorkflowError("Cannot reach GitHub; check connectivity before retrying", 502) from None
        if not response.is_success:
            raise WorkflowError(f"GitHub request failed (HTTP {response.status_code}); check App access", 502)
        return response.json()

    def file(self, client, repository, path, ref):
        result = self.request(client, "GET", f"/repos/{repository}/contents/{quote(path, safe='/')}",
                              params={"ref": ref})
        if not isinstance(result, dict) or result.get("encoding") != "base64":
            raise WorkflowError("Mapped Terraform source is not a regular supported-size file")
        return base64.b64decode(result["content"]).decode("utf-8"), result["sha"]

    def snapshot(self, binding):
        repository = binding["repository"]
        with self.client(repository) as client:
            repo = self.request(client, "GET", f"/repos/{repository}")
            branch = repo["default_branch"]
            commit = self.request(client, "GET", f"/repos/{repository}/commits/{quote(branch, safe='')}")["sha"]
            mapping, _ = self.file(client, repository, "cloudpilot.json", commit)
            matches = [item for item in json.loads(mapping)["resources"]
                       if item["resource_id"] == binding["resource_id"]]
            if len(matches) != 1 or any(matches[0].get(key) != binding[key] for key in (
                "terraform_address", "variables_file", "variable",
            )):
                raise WorkflowError("Repository mapping differs from the registered resource")
            main_path = matches[0]["terraform_file"]
            if main_path != "main.tf":
                raise WorkflowError("This integration currently validates a root main.tf module")
            files = {}
            for path in ("main.tf", ".terraform.lock.hcl", binding["variables_file"]):
                files[path], _ = self.file(client, repository, path, commit)
            tree = self.request(client, "GET", f"/repos/{repository}/git/trees/{commit}", params={"recursive": "1"})
            root_terraform = {item["path"] for item in tree["tree"]
                              if "/" not in item["path"] and item["path"].endswith((".tf", ".tf.json"))}
            if tree.get("truncated") or root_terraform != {"main.tf"}:
                raise WorkflowError("Only the mapped single root Terraform module is supported")
            return {"repository": repository, "base_branch": branch, "base_sha": commit, "files": files,
                    "mapping": matches[0]}

    def current_sha(self, binding):
        repository = binding["repository"]
        with self.client(repository) as client:
            branch = self.request(client, "GET", f"/repos/{repository}")["default_branch"]
            return self.request(client, "GET", f"/repos/{repository}/commits/{quote(branch, safe='')}")["sha"]

    def create_pr(self, proposal, checkpoint):
        binding = proposal["binding"]
        repository = binding["repository"]
        branch = "codex/cloudpilot-" + proposal["id"]
        snapshot = proposal["terraform"]
        with self.client(repository) as client:
            existing = self.request(client, "GET", f"/repos/{repository}/pulls", params={
                "state": "all", "head": repository.split("/")[0] + ":" + branch,
            })
            if existing:
                return {"url": existing[0]["html_url"], "number": existing[0]["number"], "branch": branch}
            self.request(client, "POST", f"/repos/{repository}/git/refs", json={
                "ref": "refs/heads/" + branch, "sha": snapshot["base_sha"],
            })
            checkpoint("branch_created", {"branch": branch})
            _, sha = self.file(client, repository, binding["variables_file"], branch)
            self.request(client, "PUT", f"/repos/{repository}/contents/{quote(binding['variables_file'], safe='/')}",
                json={"branch": branch, "sha": sha, "message": "Apply approved CloudPilot resize proposal",
                      "content": base64.b64encode(proposal["patch"]["after"].encode()).decode()})
            checkpoint("terraform_committed", {"branch": branch})
            before = proposal["before"]["instance_type"]
            target = proposal["recommendation"]["target_instance_type"]
            body = (f"Resize the mapped LocalStack demo instance from `{before}` to `{target}` by updating "
                    f"`{binding['variable']}` in `{binding['variables_file']}`.\n\n"
                    f"Proposal: `{proposal['id']}`. Approval digest: `{proposal['digest']}`.\n"
                    f"Evidence: `{proposal['recommendation']['evidence']['version']}` "
                    f"(source: {proposal['recommendation']['evidence']['source']}).\n\n"
                    "Validation: Terraform fmt and validate passed against the pinned AWS provider. "
                    "No Terraform plan or workload benchmark was run for this candidate.\n\n"
                    "The customer reviews, merges and applies this change. Creating this PR does not change infrastructure. "
                    "To undo after apply, restore the previous variable value in a new reviewed PR.")
            origin = proposal["recommendation"]["evidence"].get("engine_reference")
            if origin:
                body += (f"\n\nEngine source: `{origin['recommendation_id']}` / `{origin['source_resource_id']}`; "
                         f"candidate `{origin['target_plan_id']}`; historical cutoff `{origin['analysis_as_of']}`. "
                         "This PR tests the target CPU/RAM shape on the LocalStack fixture only. "
                         "It does not authorize a Utho production change or claim equivalent hardware performance.\n\n"
                         "Unresolved provider checks:\n" + "\n".join("- " + item for item in origin["provider_blockers"]))
            result = self.request(client, "POST", f"/repos/{repository}/pulls", json={
                "title": f"CloudPilot: resize {binding['resource_id']} to {target}", "body": body,
                "head": branch, "base": snapshot["base_branch"],
            })
            checkpoint("pr_created", {"url": result["html_url"]})
            return {"url": result["html_url"], "number": result["number"], "branch": branch}
