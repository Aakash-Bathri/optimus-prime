"""Preserve engine gates while testing a capacity candidate in the isolated lab."""

from app.execution.contracts import EngineReference, LAB_CAPACITIES, WorkflowError


def lab_type(candidate):
    return next((name for name, shape in LAB_CAPACITIES.items()
                 if shape == (candidate.plan.vcpu, candidate.plan.memory_gib)), None)


def lab_candidates(engine, recommendation_id):
    finding = engine.recommendation(recommendation_id)
    return {"recommendation_id": finding.id, "decision": finding.decision,
            "source_resource_id": finding.resource_id, "analysis_as_of": finding.provenance.analysis_as_of.isoformat(),
            "production_ready": finding.ready, "provider_blockers": finding.blockers,
            "candidates": [{"plan_id": item.plan.id, "vcpu": item.plan.vcpu,
                "memory_gib": item.plan.memory_gib, "lab_instance_type": lab_type(item),
                "capacity_eligible": item.capacity_eligible,
                "lab_eligible": bool(item.capacity_eligible and lab_type(item)),
                "checks": [check.model_dump(mode="json") for check in item.checks]}
                for item in finding.candidates]}


def selected(engine, recommendation_id, plan_id):
    finding = engine.recommendation(recommendation_id)
    if finding.decision != "accepted":
        raise WorkflowError("Queue this engine finding for review before preparing a lab test")
    if finding.action not in ("resize", "capacity_review") or finding.outcome in ("no_action", "insufficient_data", "unsupported"):
        raise WorkflowError("This finding does not support a capacity change")
    resource = engine.resource(finding.resource_id)
    if not resource.owner or resource.owner.lower() in ("unknown", "unassigned"):
        raise WorkflowError("The source resource needs a known owner before a lab proposal")
    candidate = next((item for item in finding.candidates if item.plan.id == plan_id), None)
    if candidate is None or not candidate.capacity_eligible or not lab_type(candidate):
        raise WorkflowError("Candidate must pass engine capacity checks and have an exact supported lab CPU/RAM shape")
    return finding, candidate


def reference(finding, candidate):
    return EngineReference(recommendation_id=finding.id, recommendation_version=finding.version,
        decision_revision=finding.decision_revision, source_resource_id=finding.resource_id,
        target_plan_id=candidate.plan.id, analysis_as_of=finding.provenance.analysis_as_of,
        provider_blockers=[check.message for check in candidate.checks if check.status != "passed"])


def revalidate(engine, evidence, target):
    origin = evidence.engine_reference
    if origin is None or engine is None:
        raise WorkflowError("Engine-linked evidence requires a server-side source reference")
    finding, candidate = selected(engine, origin.recommendation_id, origin.target_plan_id)
    if origin != reference(finding, candidate) or target != lab_type(candidate):
        raise WorkflowError("Engine evidence or review decision changed; prepare and approve again")
