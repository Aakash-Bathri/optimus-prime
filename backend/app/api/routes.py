import csv
import io
import json
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from app.engine.service import CloudPilot, Filters
from app.engine.expenses import data_sources, expenses
from app.models.contracts import (
    Alert, DecisionRequest, Page, ProviderPlan, Recommendation, RecommendationSummary, Resource, SimulationRequest,
)

router = APIRouter(prefix="/api")


def service(request: Request) -> CloudPilot:
    return request.app.state.cloudpilot


def filters(
    environment: Literal["production", "staging", "development"] | None = None,
    region: str | None = None, team: str | None = None,
    resource_type: Literal["vm", "block_volume", "public_ip", "gpu"] | None = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    data_source: str | None = None,
) -> Filters:
    return Filters(environment, region, team, resource_type, search, data_source)


Service = Annotated[CloudPilot, Depends(service)]
Scope = Annotated[Filters, Depends(filters)]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/health", tags=["system"])
def health(app: Service) -> dict:
    dataset = app.dataset()
    return {"status": "ok", "service": "cloudpilot", "version": "0.2.0", "dataset_version": dataset["version"], "mode": dataset["mode"]}


@router.get("/dataset", tags=["system"])
def dataset(app: Service) -> dict:
    return app.dataset()


@router.get("/data-sources", tags=["system"])
def sources(app: Service) -> dict:
    return data_sources(app.database_path, app.dataset(), app.resources())


@router.get("/expenses", tags=["finops"])
def cost_explorer(
    app: Service, scope: Scope, start: date | None = None, end: date | None = None,
    granularity: Literal["day", "week", "month"] = "day",
    breakdown: Literal["data_source", "resource_type", "environment", "region", "team"] = "data_source",
) -> dict:
    try:
        return expenses(app.database_path, app.resources(scope), start=start, end=end, granularity=granularity, breakdown=breakdown)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/summary", tags=["overview"])
def summary(app: Service, scope: Scope) -> dict:
    return app.summary(scope)


@router.get("/metrics", tags=["telemetry"])
def estate_metrics(app: Service, scope: Scope, resolution: Literal["day", "hour"] = "day") -> dict:
    return app.series([resource.id for resource in app.resources(scope) if resource.type == "vm"], resolution)


@router.get("/resources", response_model=Page[Resource], tags=["inventory"])
def resources(app: Service, scope: Scope, limit: Limit = 50, offset: Offset = 0):
    items = app.resources(scope)
    return Page(items=items[offset:offset + limit], total=len(items), limit=limit, offset=offset)


@router.get("/resources/{resource_id}", tags=["inventory"])
def resource_detail(resource_id: str, app: Service) -> dict:
    return app.detail(resource_id)


@router.get("/resources/{resource_id}/metrics", tags=["telemetry"])
def resource_metrics(resource_id: str, app: Service, resolution: Literal["day", "hour"] = "day") -> dict:
    resource = app.resource(resource_id)
    return app.series([resource.id] if resource.type == "vm" else [], resolution)


@router.get("/plans", response_model=list[ProviderPlan], tags=["catalogue"])
def plans(app: Service):
    return app.plans()


@router.get("/recommendations", response_model=Page[RecommendationSummary], tags=["recommendations"])
def recommendations(
    app: Service, scope: Scope, limit: Limit = 50, offset: Offset = 0,
    outcome: Literal["recommendation", "blocked", "insufficient_data", "no_action", "unsupported"] | None = None,
    decision: Literal["pending", "accepted", "rejected"] | None = None,
    action: Literal["resize", "capacity_review", "idle_review", "orphan_review", "observe"] | None = None,
):
    items = app.recommendations(scope, outcome=outcome, decision=decision, action=action)
    return Page(items=items[offset:offset + limit], total=len(items), limit=limit, offset=offset)


@router.get("/recommendations/{recommendation_id}", response_model=Recommendation, tags=["recommendations"])
def recommendation(recommendation_id: str, app: Service):
    return app.recommendation(recommendation_id)


@router.patch("/recommendations/{recommendation_id}", response_model=Recommendation, tags=["recommendations"])
def decide(recommendation_id: str, body: DecisionRequest, app: Service):
    return app.decide(recommendation_id, body)


@router.post("/simulate", tags=["simulation"])
def simulate(body: SimulationRequest, app: Service) -> dict:
    return app.simulate(body)


@router.get("/optimization-plan", tags=["planning"])
def optimization_plan(app: Service, scope: Scope) -> dict:
    return app.plan(scope)


def csv_text(value):
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@router.get("/optimization-plan/export", tags=["planning"])
def export(app: Service, scope: Scope, format: Literal["json", "csv"] = "json"):
    payload = app.export(scope)
    headers = {"Content-Disposition": f'attachment; filename="cloudpilot-plan.{format}"'}
    if format == "json":
        return Response(json.dumps(payload, indent=2), media_type="application/json", headers=headers)
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    columns = ["resource_id", "resource_name", "action", "outcome", "decision", "review_only", "current_plan_id", "target_plan_id", "current_monthly_cost", "target_monthly_cost", "modeled_monthly_savings", "conditional_monthly_savings", "blockers", "prerequisites"]
    writer.writerow([*columns, "currency", "cost_basis", "dataset_version", "policy_version", "assumptions", "generated_at"])
    for item in payload["plan"]["items"]:
        values = []
        for column in columns:
            value = item[column]
            if isinstance(value, list):
                value = " | ".join(value)
            monetary = column in {"current_monthly_cost", "target_monthly_cost", "modeled_monthly_savings", "conditional_monthly_savings"}
            values.append(value if monetary else csv_text(value))
        writer.writerow([*values, *map(csv_text, ["INR", payload["dataset"]["cost_basis"], payload["dataset"]["version"], payload["dataset"]["policy"]["version"], " | ".join(payload["dataset"]["assumptions"]), payload["generated_at"]])])
    return Response(stream.getvalue(), media_type="text/csv", headers=headers)


@router.get("/alerts", response_model=Page[Alert], tags=["alerts"])
def alerts(app: Service, scope: Scope, limit: Limit = 50, offset: Offset = 0):
    items = app.alerts(scope)
    return Page(items=items[offset:offset + limit], total=len(items), limit=limit, offset=offset)


@router.get("/audit", tags=["governance"])
def audit(app: Service, limit: Limit = 100) -> list[dict]:
    return app.audit(limit)

