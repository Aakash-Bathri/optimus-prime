"""Authenticated local operator API; external integrations remain optional at startup."""

import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request

from app.execution.contracts import Binding, Decision, EnginePrepareRequest, ExecuteRequest, PrepareRequest, WorkflowError


def operator(request: Request, authorization: Annotated[str | None, Header()] = None):
    expected = request.app.state.settings.execution_token.get_secret_value()
    if not expected:
        raise WorkflowError("Set CLOUDPILOT_EXECUTION_TOKEN in .env to enable execution endpoints", 503)
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not secrets.compare_digest(supplied, expected):
        raise WorkflowError("A valid local operator token is required", 401)
    return request.app.state.execution


router = APIRouter(prefix="/api/execution", tags=["Person 5 execution"], dependencies=[Depends(operator)])


@router.get("/resources")
async def resources(service=Depends(operator)):
    return await service.resources()


@router.get("/discover")
async def discover(service=Depends(operator)):
    return await service.discover()


@router.post("/resources")
async def register(binding: Binding, service=Depends(operator)):
    return await service.register(binding)


@router.post("/demo/setup")
async def setup_demo(service=Depends(operator)):
    return await service.setup_demo()


@router.get("/demo/recommendation/{resource_id}")
def demo_recommendation(resource_id: str, action: Literal["resize", "stop", "start"] = "resize",
                        target: Literal["m5.large", "m5.xlarge", "m5.2xlarge"] = "m5.xlarge",
                        service=Depends(operator)):
    if not service.store.binding(resource_id):
        raise WorkflowError("Resource is not registered", 404)
    return service.stub(resource_id, action, target)


@router.post("/proposals")
async def prepare(body: PrepareRequest, service=Depends(operator)):
    return await service.prepare(body)


@router.get("/proposals")
def proposals(service=Depends(operator)):
    return service.store.proposals()


@router.get("/engine/candidates/{recommendation_id}")
def engine_candidates(recommendation_id: str, service=Depends(operator)):
    from app.execution.engine_bridge import lab_candidates
    if service.engine is None:
        raise WorkflowError("Recommendation engine is not connected", 503)
    return lab_candidates(service.engine, recommendation_id)


@router.post("/engine/proposals")
async def prepare_engine(body: EnginePrepareRequest, service=Depends(operator)):
    return await service.prepare_engine(body)


@router.get("/proposals/{identifier}")
def proposal(identifier: str, service=Depends(operator)):
    return service.store.get(identifier)


@router.post("/proposals/{identifier}/decision")
def decide(identifier: str, body: Decision, service=Depends(operator)):
    return service.decide(identifier, body)


@router.post("/proposals/{identifier}/execute")
async def execute(identifier: str, body: ExecuteRequest, service=Depends(operator)):
    return await service.execute(identifier, body.digest)


@router.post("/proposals/{identifier}/rollback")
async def rollback(identifier: str, mode: Literal["llm", "scripted"] = "llm", service=Depends(operator)):
    return await service.rollback(identifier, mode)


@router.post("/proposals/{identifier}/acknowledge-recovery")
async def acknowledge(identifier: str, body: ExecuteRequest, service=Depends(operator)):
    return await service.acknowledge_recovery(identifier, body.digest)


@router.get("/audit")
def audit(proposal_id: str | None = None, service=Depends(operator)):
    return service.store.history(proposal_id)
