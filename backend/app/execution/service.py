"""The shared preview/approval/execute boundary used by REST and the dashboard."""

import asyncio
from datetime import timedelta
import hashlib
import json
from uuid import uuid4

from app.agent.planner import Planner
from app.execution.contracts import Binding, Evidence, Recommendation, WorkflowError, utcnow
from app.execution.github import GitHub
from app.execution.store import Store
from app.execution.terraform import Terraform
from app.mcp.localstack import localstack


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ExecutionService:
    def __init__(self, path, config, cloud_factory=None, github=None, terraform=None, planner=None, engine=None):
        self.store = Store(path)
        self.config = config
        self.cloud_factory = cloud_factory or (lambda: localstack(config))
        self.github = github or GitHub(config)
        self.terraform = terraform or Terraform()
        self.planner = planner or Planner(config)
        self.engine = engine

    @staticmethod
    def guard(binding, current):
        tags = current["tags"]
        if tags.get("CloudPilotDemo") != "true":
            raise WorkflowError("Only tagged LocalStack demo resources are supported", 403)
        if tags.get("CloudPilotId") != binding["resource_id"] or tags.get("Management") != binding["management"]:
            raise WorkflowError("Live resource identity/management differs from its explicit registration")
        if not tags.get("Owner") or tags["Owner"].lower() in ("unknown", "unassigned"):
            raise WorkflowError("Resource ownership must be known before preparing a change")
        if current["state"] not in ("running", "stopped"):
            raise WorkflowError("Resource is not in a stable running/stopped state")

    def evidence(self, recommendation):
        record = Recommendation.model_validate(recommendation).evidence
        if record.source == "engine_lab":
            from app.execution.engine_bridge import revalidate
            revalidate(self.engine, record, recommendation.get("target_instance_type"))
        now = utcnow()
        max_age = int(self.config.get("CLOUDPILOT_EVIDENCE_MAX_AGE_SECONDS", "3600"))
        if not record.checks_passed:
            raise WorkflowError("Engine checks did not pass; the agent cannot override them")
        if record.observed_at > now + timedelta(seconds=30) or record.expires_at <= now:
            raise WorkflowError("Evidence is expired or has a future observation time")
        if (now - record.observed_at).total_seconds() > max_age:
            raise WorkflowError("Evidence is too old; request a fresh recommendation")

    async def register(self, binding):
        async with self.cloud_factory() as cloud:
            current = await cloud.inspect(binding.provider_id)
        body = binding.model_dump(mode="json")
        self.guard(body, current)
        if binding.management == "terraform":
            await asyncio.to_thread(self.github.snapshot, body)
        return self.store.bind(binding)

    async def resources(self):
        async with self.cloud_factory() as cloud:
            inventory = await cloud.inventory()
        by_id = {item["provider_id"]: item for item in inventory}
        return [{**binding, "current": by_id.get(binding["provider_id"])} for binding in self.store.bindings()]

    async def discover(self):
        async with self.cloud_factory() as cloud:
            return [item for item in await cloud.inventory() if item["tags"].get("CloudPilotDemo") == "true"]

    async def setup_demo(self, management_filter=None):
        # Demo tags explicitly contain the management source; ordinary onboarding requires Binding.
        resources = await self.discover()
        result = []
        for resource_id, management in (("demo-api-01", "terraform"), ("demo-manual-01", "manual")):
            if management_filter and management != management_filter:
                continue
            matches = [item for item in resources if item["tags"].get("CloudPilotId") == resource_id
                       and item["tags"].get("Management") == management]
            if len(matches) != 1:
                raise WorkflowError("Demo fixture is missing or duplicated; run bash infra/seed_demo.sh --terraform (macOS/Linux) or infra/seed_demo.ps1 (Windows)")
            mapping = {"repository": self.config.get("CLOUDPILOT_GITHUB_TEST_REPO"),
                       "terraform_address": "aws_instance.production_api",
                       "variables_file": "terraform.tfvars.json", "variable": "api_instance_type"} if management == "terraform" else {}
            result.append(await self.register(Binding(resource_id=resource_id,
                provider_id=matches[0]["provider_id"], management=management, **mapping)))
        return result

    def stub(self, resource_id, action="resize", target="m5.xlarge"):
        now = utcnow()
        return Recommendation(id="stub-" + str(uuid4()), resource_id=resource_id, action=action,
            target_instance_type=target if action == "resize" else None,
            evidence=Evidence(version="localstack-control-plane-demo-v1", observed_at=now,
                expires_at=now + timedelta(minutes=30), checks_passed=True, source="stub",
                reason="Explicit demo recommendation to test the approval and execution path. "
                       "No measured workload safety, production suitability or savings are asserted."))

    async def prepare(self, request):
        self.store.audit(None, "preparation_requested", {
            "resource_id": request.recommendation.resource_id,
            "recommendation_id": request.recommendation.id, "mode": request.mode,
            "evidence_version": request.recommendation.evidence.version,
        })
        try:
            return await self._prepare(request)
        except WorkflowError as error:
            self.store.audit(None, "preparation_blocked", {"resource_id": request.recommendation.resource_id,
                                                           "reason": str(error)})
            raise
        except Exception as error:
            self.store.audit(None, "preparation_failed", {"resource_id": request.recommendation.resource_id,
                                                          "error_type": type(error).__name__})
            raise WorkflowError("Preparation failed; check the integration settings and audit before retrying", 502) from None

    async def prepare_engine(self, request):
        from app.execution.contracts import PrepareRequest
        from app.execution.engine_bridge import selected, reference, lab_type
        if self.engine is None:
            raise WorkflowError("Recommendation engine is not connected", 503)
        finding, candidate = selected(self.engine, request.recommendation_id, request.target_plan_id)
        now = utcnow()
        recommendation = Recommendation(id="lab-" + str(uuid4()), resource_id=request.binding_resource_id,
            action="resize", target_instance_type=lab_type(candidate),
            evidence=Evidence(version=finding.version, observed_at=now, expires_at=now + timedelta(minutes=30),
                checks_passed=True, source="engine_lab", engine_reference=reference(finding, candidate),
                reason=(f"LocalStack-only test of engine candidate {candidate.plan.id} for {finding.resource_id}. "
                    f"Capacity checks passed on historical data ending {finding.provenance.analysis_as_of.isoformat()}. "
                    "The lab instance mirrors the target CPU/RAM shape only; provider, storage, hardware performance, "
                    "production authorization and savings remain unverified. " + finding.explanation)[:2000]))
        return await self.prepare(PrepareRequest(recommendation=recommendation, mode=request.mode))

    async def _prepare(self, request):
        recommendation = request.recommendation.model_dump(mode="json")
        self.evidence(recommendation)
        binding = self.store.binding(recommendation["resource_id"])
        if not binding:
            raise WorkflowError("Register this resource with terraform/manual management first", 404)
        async with self.cloud_factory() as cloud:
            current = await cloud.inspect(binding["provider_id"])
        self.guard(binding, current)
        self.store.audit(None, "resource_inspected", {"resource_id": binding["resource_id"], "snapshot_digest": digest(current)})
        action = recommendation["action"]
        if action == "resize" and current["instance_type"] == recommendation["target_instance_type"]:
            raise WorkflowError("Resource already has the requested instance type")
        if action in ("start", "stop") and current["state"] == ("running" if action == "start" else "stopped"):
            raise WorkflowError("Resource already has the requested state")
        terraform = {}
        patch = None
        if binding["management"] == "terraform":
            if action != "resize":
                raise WorkflowError("Terraform mapping currently supports resize; lifecycle actions need a separate mapping")
            terraform = await asyncio.to_thread(self.github.snapshot, binding)
            patch = await asyncio.to_thread(self.terraform.prepare, terraform, binding,
                current["instance_type"], recommendation["target_instance_type"])
            self.store.audit(None, "terraform_validated", {"resource_id": binding["resource_id"],
                "base_sha": terraform["base_sha"], "validation": patch["validation"]})
        plan = await self.planner.plan(recommendation, binding, current, terraform, request.mode)
        action_steps = self.steps(recommendation, current, binding)
        immutable = {"binding": binding, "before": current, "recommendation": recommendation,
                     "terraform": terraform, "patch": patch, "steps": action_steps,
                     "evidence_source": recommendation["evidence"]["source"]}
        return self.store.create({**immutable, "digest": digest(immutable), "agent": plan,
            "rollback": "Prepare a fresh inverse proposal and approve its exact preview. "
                        "A resize may stop the VM. A Terraform PR requires a new revert PR after customer apply."})

    @staticmethod
    def steps(recommendation, current, binding):
        if binding["management"] == "terraform":
            return ["Create a branch from the reviewed GitHub commit", "Commit the validated variable diff",
                    "Open a pull request", "Customer reviews, merges and applies Terraform"]
        if recommendation["action"] == "resize":
            return (["Stop instance and wait for stopped"] if current["state"] == "running" else []) + [
                "Change instance type to " + recommendation["target_instance_type"],
            ] + (["Start instance and wait for running"] if current["state"] == "running" else []) + [
                "Read LocalStack again and verify instance type and original running/stopped state"]
        return [recommendation["action"].capitalize() + " instance", "Read LocalStack again and verify state"]

    def decide(self, identifier, decision):
        proposal = self.store.get(identifier)
        if proposal["digest"] != decision.digest:
            raise WorkflowError("Approval digest differs from the exact preview")
        if decision.decision == "approve":
            self.evidence(proposal["recommendation"])
        status = "APPROVED" if decision.decision == "approve" else "REJECTED"
        return self.store.transition(identifier, ("AWAITING_APPROVAL",), status,
            decision={"actor": "local_operator", "at": utcnow().isoformat(), "digest": decision.digest})

    async def execute(self, identifier, approved_digest):
        proposal, claimed = self.store.claim(identifier, approved_digest)
        if not claimed:
            return proposal
        mutated = False

        def checkpoint(event, details):
            nonlocal mutated
            if event in ("stop_requested", "start_requested", "resize_requested", "branch_created"):
                mutated = True
            self.store.audit(identifier, event, details)

        try:
            self.evidence(proposal["recommendation"])
            binding = proposal["binding"]
            if self.store.binding(binding["resource_id"]) != binding:
                raise WorkflowError("Resource registration changed after preview")
            async with self.cloud_factory() as cloud:
                current = await cloud.inspect(binding["provider_id"])
                self.guard(binding, current)
                if current != proposal["before"]:
                    raise WorkflowError("Resource configuration changed after preview; prepare and approve again")
                if binding["management"] == "terraform":
                    if await asyncio.to_thread(self.github.current_sha, binding) != proposal["terraform"]["base_sha"]:
                        raise WorkflowError("GitHub base commit changed after preview; prepare and approve again")
                    result = await asyncio.to_thread(self.github.create_pr, proposal, checkpoint)
                    return self.store.transition(identifier, ("EXECUTING",), "PR_CREATED", result=result)
                identifier_in_cloud = binding["provider_id"]
                action = proposal["recommendation"]["action"]
                if action == "resize":
                    if current["state"] == "running":
                        checkpoint("stop_requested", {})
                        await cloud.state(identifier_in_cloud, "stop")
                        await cloud.wait(identifier_in_cloud, "stopped")
                    checkpoint("resize_requested", {"target": proposal["recommendation"]["target_instance_type"]})
                    await cloud.resize(identifier_in_cloud, proposal["recommendation"]["target_instance_type"])
                    if current["state"] == "running":
                        checkpoint("start_requested", {})
                        await cloud.state(identifier_in_cloud, "start")
                        await cloud.wait(identifier_in_cloud, "running")
                    expected_type = proposal["recommendation"]["target_instance_type"]
                    expected_state = current["state"]
                else:
                    checkpoint(action + "_requested", {})
                    await cloud.state(identifier_in_cloud, action)
                    expected_state = "running" if action == "start" else "stopped"
                    await cloud.wait(identifier_in_cloud, expected_state)
                    expected_type = current["instance_type"]
                after = await cloud.inspect(identifier_in_cloud)
                if after["instance_type"] != expected_type or after["state"] != expected_state:
                    raise WorkflowError("Post-change verification failed; inspect LocalStack before retrying", 502)
                return self.store.transition(identifier, ("EXECUTING",), "APPLIED", result={
                    "after": after, "verified_at": utcnow().isoformat(), "provider": "localstack",
                    "workload_performance_verified": False})
        except BaseException as error:
            message = str(error) if isinstance(error, WorkflowError) else "Integration failed; inspect the audit and live resource"
            status = "RECOVERY_REQUIRED" if mutated or not isinstance(error, Exception) else "STALE" if isinstance(error, WorkflowError) and error.status == 409 else "FAILED"
            self.store.transition(identifier, ("EXECUTING",), status, error=message)
            if status != "RECOVERY_REQUIRED":
                self.store.release(identifier)
            if isinstance(error, WorkflowError):
                raise
            if not isinstance(error, Exception):
                raise
            raise WorkflowError(message, 502) from None
        finally:
            if self.store.get(identifier)["status"] in ("APPLIED", "PR_CREATED"):
                self.store.release(identifier)

    async def acknowledge_recovery(self, identifier, approved_digest):
        proposal = self.store.get(identifier)
        if proposal["status"] != "RECOVERY_REQUIRED" or proposal["digest"] != approved_digest:
            raise WorkflowError("Only an interrupted execution can be acknowledged")
        async with self.cloud_factory() as cloud:
            current = await cloud.inspect(proposal["binding"]["provider_id"])
        self.store.audit(identifier, "recovery_inspected", {"current": current, "actor": "local_operator"})
        result = self.store.transition(identifier, ("RECOVERY_REQUIRED",), "FAILED", recovery_snapshot=current)
        self.store.release(identifier)
        return result

    async def rollback(self, identifier, mode):
        from app.execution.contracts import PrepareRequest
        proposal = self.store.get(identifier)
        if proposal["status"] != "APPLIED" or proposal["binding"]["management"] != "manual":
            raise WorkflowError("Only an applied manual change supports this inverse preview")
        original = proposal["recommendation"]
        action = "resize" if original["action"] == "resize" else "start" if original["action"] == "stop" else "stop"
        recommendation = self.stub(proposal["binding"]["resource_id"], action, proposal["before"]["instance_type"])
        return await self.prepare(PrepareRequest(recommendation=recommendation, mode=mode))
