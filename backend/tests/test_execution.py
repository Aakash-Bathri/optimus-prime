import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import timedelta
import shutil

import pytest
from fastapi.testclient import TestClient

from app.agent.planner import Planner
from app.config import Settings
from app.execution.contracts import Binding, WorkflowError, utcnow
from app.execution.service import ExecutionService
from app.execution.terraform import Terraform
from app.main import create_app


class FakeCloud:
    def __init__(self):
        self.items = {}
        self.mutations = []
        self.fail_resize = False
        self.ignore_resize = False
        for resource_id, management, identifier in (
            ("demo-manual-01", "manual", "i-11111111"),
            ("demo-api-01", "terraform", "i-22222222"),
        ):
            self.items[identifier] = {"provider_id": identifier, "instance_type": "m5.2xlarge", "state": "running",
                "tags": {"CloudPilotId": resource_id, "Management": management,
                         "CloudPilotDemo": "true", "Owner": "demo-engineer"}}

    @asynccontextmanager
    async def session(self):
        yield self

    async def inspect(self, identifier):
        return deepcopy(self.items[identifier])

    async def inventory(self):
        return deepcopy(list(self.items.values()))

    async def state(self, identifier, action):
        self.mutations.append(action)
        self.items[identifier]["state"] = "running" if action == "start" else "stopped"

    async def resize(self, identifier, target):
        self.mutations.append("resize")
        if self.fail_resize:
            raise RuntimeError("provider failed")
        if not self.ignore_resize:
            self.items[identifier]["instance_type"] = target

    async def wait(self, identifier, state):
        await asyncio.sleep(0.01)
        assert self.items[identifier]["state"] == state


class FakeGitHub:
    def __init__(self):
        self.sha = "a" * 40
        self.prs = []

    def snapshot(self, binding):
        return {"base_sha": self.sha, "base_branch": "main", "files": {}, "mapping": {}}

    def current_sha(self, binding):
        return self.sha

    def create_pr(self, proposal, checkpoint):
        self.prs.append(proposal["id"])
        checkpoint("branch_created", {"branch": "codex/test"})
        return {"url": "https://github.com/example/demo/pull/1", "number": 1, "branch": "codex/test"}


class FakeTerraform:
    def prepare(self, *arguments):
        return {"file": "terraform.tfvars.json", "before": '{}', "after": '{"api_instance_type":"m5.xlarge"}',
                "diff": "-m5.2xlarge\n+m5.xlarge", "validation": {"fmt": "passed", "validate": "passed", "plan": "not_run"}}


@pytest.fixture
def lab(tmp_path, seeded_database):
    shutil.copyfile(seeded_database, tmp_path / "execution.sqlite3")
    cloud = FakeCloud()
    github = FakeGitHub()
    service = ExecutionService(tmp_path / "execution.sqlite3", {"CLOUDPILOT_GITHUB_TEST_REPO": "example/demo"},
                               cloud_factory=cloud.session, github=github, terraform=FakeTerraform(), planner=Planner({}))
    settings = Settings(database_path=tmp_path / "execution.sqlite3", execution_token="test-operator")
    with TestClient(create_app(settings, execution_service=service)) as client:
        client.headers["Authorization"] = "Bearer test-operator"
        assert client.post("/api/execution/demo/setup").status_code == 200
        yield client, service, cloud, github


def prepare(client, resource_id="demo-manual-01", action="resize", target="m5.xlarge", edit=None):
    recommendation = client.get(f"/api/execution/demo/recommendation/{resource_id}?action={action}&target={target}").json()
    if edit:
        edit(recommendation)
    return client.post("/api/execution/proposals", json={"recommendation": recommendation, "mode": "scripted"})


def decide(client, proposal, decision="approve", digest=None):
    return client.post(f"/api/execution/proposals/{proposal['id']}/decision", json={
        "decision": decision, "digest": digest or proposal["digest"]})


def execute(client, proposal):
    return client.post(f"/api/execution/proposals/{proposal['id']}/execute", json={"digest": proposal["digest"]})


@pytest.mark.parametrize("resource", ["demo-manual-01", "demo-api-01"])
def test_rejected_or_unapproved_cannot_mutate(lab, resource):
    client, service, cloud, github = lab
    response = prepare(client, resource)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["status"] == "AWAITING_APPROVAL"
    assert execute(client, proposal).status_code == 409
    assert decide(client, proposal, digest="wrong").status_code == 409
    assert decide(client, proposal, "reject").json()["status"] == "REJECTED"
    assert execute(client, proposal).status_code == 409
    assert not cloud.mutations and not github.prs


def test_manual_resize_roundtrip_and_persistent_audit(lab):
    client, service, cloud, github = lab
    proposal = prepare(client).json()
    assert decide(client, proposal).json()["status"] == "APPROVED"
    result = execute(client, proposal)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "APPLIED"
    assert cloud.mutations == ["stop", "resize", "start"]
    assert cloud.items["i-11111111"]["instance_type"] == "m5.xlarge"
    assert execute(client, proposal).json()["status"] == "APPLIED"
    assert cloud.mutations == ["stop", "resize", "start"]
    inverse = client.post(f"/api/execution/proposals/{proposal['id']}/rollback?mode=scripted").json()
    assert inverse["status"] == "AWAITING_APPROVAL"
    assert cloud.items["i-11111111"]["instance_type"] == "m5.xlarge"
    decide(client, inverse)
    assert execute(client, inverse).json()["status"] == "APPLIED"
    assert cloud.items["i-11111111"]["instance_type"] == "m5.2xlarge"
    reloaded = ExecutionService(service.store.path, {})
    assert reloaded.store.get(proposal["id"])["status"] == "APPLIED"
    assert any(item["event"] == "resize_requested" for item in reloaded.store.history(proposal["id"]))


def test_stopped_resize_preserves_state_and_start_stop(lab):
    client, service, cloud, github = lab
    cloud.items["i-11111111"]["state"] = "stopped"
    proposal = prepare(client).json()
    decide(client, proposal)
    assert execute(client, proposal).json()["result"]["after"]["state"] == "stopped"
    assert cloud.mutations == ["resize"]
    for action, expected in (("start", "running"), ("stop", "stopped")):
        proposal = prepare(client, action=action).json()
        decide(client, proposal)
        assert execute(client, proposal).json()["result"]["after"]["state"] == expected


def test_terraform_opens_one_pr_and_never_applies(lab):
    client, service, cloud, github = lab
    proposal = prepare(client, "demo-api-01").json()
    assert proposal["patch"]["validation"]["plan"] == "not_run"
    assert [item["tool"] for item in proposal["agent"]["tool_calls"]] == ["inspect_resource", "read_terraform", "prepare_change"]
    decide(client, proposal)
    assert execute(client, proposal).json()["status"] == "PR_CREATED"
    assert execute(client, proposal).json()["status"] == "PR_CREATED"
    assert len(github.prs) == 1
    assert not cloud.mutations


@pytest.mark.parametrize("case", ["live_state", "ownership", "binding", "github", "expired"])
def test_stale_approval_blocks_mutation(lab, case):
    client, service, cloud, github = lab
    proposal = prepare(client, "demo-api-01" if case == "github" else "demo-manual-01").json()
    decide(client, proposal)
    if case == "live_state":
        cloud.items["i-11111111"]["instance_type"] = "m5.large"
    elif case == "ownership":
        cloud.items["i-11111111"]["tags"]["Owner"] = "unknown"
    elif case == "binding":
        service.store.bind(Binding(resource_id="demo-manual-01", management="manual", provider_id="i-33333333"))
    elif case == "github":
        github.sha = "b" * 40
    else:
        # Advance the service clock without editing the persisted immutable proposal.
        from unittest.mock import patch
        with patch("app.execution.service.utcnow", return_value=utcnow() + timedelta(hours=2)):
            assert execute(client, proposal).status_code == 409
        assert not cloud.mutations and not github.prs
        return
    assert execute(client, proposal).status_code == 409
    assert not cloud.mutations and not github.prs
    assert service.store.get(proposal["id"])["status"] == "STALE"


@pytest.mark.parametrize("edit", [
    lambda recommendation: recommendation["evidence"].update(checks_passed=False),
    lambda recommendation: recommendation["evidence"].update(expires_at=(utcnow() - timedelta(seconds=1)).isoformat(), observed_at=(utcnow() - timedelta(hours=1)).isoformat()),
    lambda recommendation: recommendation["evidence"].update(observed_at=(utcnow() + timedelta(minutes=2)).isoformat()),
])
def test_engine_gates_are_enforced(lab, edit):
    client, service, cloud, github = lab
    assert prepare(client, edit=edit).status_code == 409
    assert not service.store.proposals() and not cloud.mutations and not github.prs


def test_registration_does_not_guess_management(lab):
    client, service, cloud, github = lab
    response = client.post("/api/execution/resources", json={"resource_id": "demo-api-01",
        "provider_id": "i-22222222", "management": "manual"})
    assert response.status_code == 409
    assert client.post("/api/execution/resources", json={"resource_id": "demo-api-01", "provider_id": "i-22222222"}).status_code == 422
    assert prepare(client, action="delete").status_code != 200


@pytest.mark.parametrize("failure", ["fail_resize", "ignore_resize"])
def test_partial_failure_holds_lease_until_inspected(lab, failure):
    client, service, cloud, github = lab
    proposal = prepare(client).json()
    decide(client, proposal)
    setattr(cloud, failure, True)
    assert execute(client, proposal).status_code == 502
    assert service.store.get(proposal["id"])["status"] == "RECOVERY_REQUIRED"
    assert execute(client, proposal).status_code == 409
    # Explicit acknowledgement records fresh state, marks failed and releases the lease.
    response = client.post(f"/api/execution/proposals/{proposal['id']}/acknowledge-recovery", json={"digest": proposal["digest"]})
    assert response.status_code == 200 and response.json()["status"] == "FAILED"
    assert "recovery_snapshot" in response.json()


def test_concurrent_claims_cannot_execute_same_resource(lab):
    client, service, cloud, github = lab
    first = prepare(client).json()
    second = prepare(client).json()
    decide(client, first)
    decide(client, second)

    async def race():
        return await asyncio.gather(service.execute(first["id"], first["digest"]),
                                    service.execute(second["id"], second["digest"]), return_exceptions=True)
    results = asyncio.run(race())
    assert sum(isinstance(result, WorkflowError) for result in results) == 1
    assert cloud.mutations == ["stop", "resize", "start"]


def test_authentication_and_restart_recovery(lab):
    client, service, cloud, github = lab
    assert client.get("/api/execution/proposals", headers={"Authorization": "Bearer bad"}).status_code == 401
    proposal = prepare(client).json()
    decide(client, proposal)
    service.store.claim(proposal["id"], proposal["digest"])
    service.store.recover_interrupted()
    assert service.store.get(proposal["id"])["status"] == "RECOVERY_REQUIRED"


def test_untrusted_terraform_template_is_refused_before_running_tools():
    with pytest.raises(WorkflowError, match="supported demo template"):
        Terraform().prepare({"files": {"main.tf": 'provider "external" {}'}}, {}, "m5.2xlarge", "m5.xlarge")


@pytest.mark.parametrize("wrong_target", [False, True])
def test_llm_tool_arguments_cannot_override_recommendation(lab, monkeypatch, wrong_target):
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langchain_core.messages import AIMessage

    class Model(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    client, service, cloud, github = lab
    recommendation = service.stub("demo-manual-01").model_dump(mode="json")
    responses = [AIMessage(content="", tool_calls=[{"name": "inspect_resource", "args": {}, "id": "inspect"}]),
                 AIMessage(content="", tool_calls=[{"name": "prepare_change", "id": "prepare", "args": {
                     "resource_id": "demo-manual-01", "action": "resize",
                     "target_instance_type": "m5.large" if wrong_target else "m5.xlarge",
                     "explanation": "Stub demo only; no workload safety claims.",
                 }}])]
    monkeypatch.setattr("app.agent.planner.ChatOpenAI", lambda **kwargs: Model(messages=iter(responses)))
    service.planner.config = {"OPENAI_API_KEY": "test-only", "OPENAI_BASE_URL": "http://unused", "CLOUDPILOT_LLM_MODEL": "fake"}
    response = client.post("/api/execution/proposals", json={"recommendation": recommendation, "mode": "llm"})
    assert response.status_code == (409 if wrong_target else 200)
    assert not cloud.mutations and not github.prs


def test_approval_expiry_does_not_grant_execution(lab):
    from unittest.mock import patch
    client, service, cloud, github = lab
    proposal = prepare(client).json()
    with patch("app.execution.service.utcnow", return_value=utcnow() + timedelta(hours=2)):
        assert decide(client, proposal).status_code == 409
    assert service.store.get(proposal["id"])["status"] == "AWAITING_APPROVAL"


def test_integration_failure_is_visible_and_audited(lab, monkeypatch):
    client, service, cloud, github = lab

    async def fail(*args):
        raise RuntimeError("integration failure")

    monkeypatch.setattr(service.planner, "plan", fail)
    response = prepare(client)
    assert response.status_code == 502 and response.json()["code"] == "execution_error"
    assert service.store.history()[0]["event"] == "preparation_failed"
    assert not service.store.proposals() and not cloud.mutations


def queued_engine_finding(client):
    finding = next(item for item in client.get('/api/recommendations?action=resize&limit=200').json()['items']
                   if item['resource_id'] == 'vm-115')
    response = client.patch('/api/recommendations/' + finding['id'], json={
        'decision': 'accepted', 'version': finding['version'], 'expected_revision': finding['decision_revision']})
    assert response.status_code == 200
    options = client.get('/api/execution/engine/candidates/' + finding['id']).json()
    target = next(item['plan_id'] for item in options['candidates']
                  if item['lab_eligible'] and item['lab_instance_type'] == 'm5.xlarge')
    return response.json(), target


@pytest.mark.parametrize('binding', ['demo-manual-01', 'demo-api-01'])
def test_real_engine_connects_to_both_execution_routes(lab, binding):
    client, service, cloud, github = lab
    finding, target = queued_engine_finding(client)
    before = client.get('/api/optimization-plan').json()
    response = client.post('/api/execution/engine/proposals', json={
        'recommendation_id': finding['id'], 'target_plan_id': target,
        'binding_resource_id': binding, 'mode': 'scripted'})
    assert response.status_code == 200, response.text
    proposal = response.json()
    evidence = proposal['recommendation']['evidence']
    assert evidence['source'] == 'engine_lab'
    assert evidence['engine_reference']['source_resource_id'] == finding['resource_id']
    assert evidence['engine_reference']['provider_blockers']
    decide(client, proposal)
    assert execute(client, proposal).json()['status'] == ('APPLIED' if binding == 'demo-manual-01' else 'PR_CREATED')
    assert client.get('/api/optimization-plan').json() == before
    assert client.get('/api/recommendations/' + finding['id']).json()['ready'] is False


def test_engine_decision_revokes_prepared_lab_approval(lab):
    client, service, cloud, github = lab
    finding, target = queued_engine_finding(client)
    proposal = client.post('/api/execution/engine/proposals', json={
        'recommendation_id': finding['id'], 'target_plan_id': target,
        'binding_resource_id': 'demo-manual-01', 'mode': 'scripted'}).json()
    decide(client, proposal)
    client.patch('/api/recommendations/' + finding['id'], json={
        'decision': 'rejected', 'version': finding['version'], 'expected_revision': finding['decision_revision']})
    assert execute(client, proposal).status_code == 409
    assert not cloud.mutations


def test_manual_registration_does_not_require_github(lab):
    client, service, cloud, github = lab
    def unavailable(binding):
        raise RuntimeError("GitHub is not configured")
    github.snapshot = unavailable
    response = client.post("/api/execution/demo/setup?management=manual")
    assert response.status_code == 200, response.text
    assert [item["resource_id"] for item in response.json()] == ["demo-manual-01"]
    proposal = prepare(client).json()
    assert decide(client, proposal).status_code == 200
    assert execute(client, proposal).json()["status"] == "APPLIED"
