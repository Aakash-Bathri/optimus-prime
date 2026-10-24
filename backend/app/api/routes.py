from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.adapters.fixtures import load_estate
from app.database import connect
from app.models.contracts import ErrorResponse, Page, ProviderPlan, Resource

router = APIRouter(prefix="/api")


@router.get("/health", tags=["system"])
def health(request: Request) -> dict[str, str]:
    with connect(request.app.state.settings.resolved_database_path) as connection:
        connection.execute("SELECT 1")
    return {"status": "ok", "service": "cloudpilot", "version": "0.1.0"}


@router.get("/resources", response_model=Page[Resource], tags=["inventory"])
def resources(
    environment: Literal["production", "staging", "development"] | None = None,
    region: str | None = None,
    team: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[Resource]:
    items = [
        resource for resource in load_estate().resources
        if (environment is None or resource.environment == environment)
        and (region is None or resource.region == region)
        and (team is None or resource.team == team)
    ]
    return Page(items=items[offset:offset + limit], total=len(items), limit=limit, offset=offset)


@router.get(
    "/resources/{resource_id}", response_model=Resource, tags=["inventory"],
    responses={404: {"model": ErrorResponse}},
)
def resource_detail(resource_id: str) -> Resource:
    for resource in load_estate().resources:
        if resource.id == resource_id:
            return resource
    raise HTTPException(status_code=404, detail="Resource not found")


@router.get("/plans", response_model=list[ProviderPlan], tags=["catalogue"])
def plans() -> list[ProviderPlan]:
    return load_estate().plans

