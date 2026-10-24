from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

T = TypeVar("T")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Page(Contract, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Resource(Contract):
    id: str
    name: str
    type: Literal["vm", "volume", "ip"]
    region: str
    environment: Literal["production", "staging", "development"]
    team: str
    owner: str | None = None
    current_plan_id: str | None = None
    configuration_revision: int = Field(default=1, ge=1)
    provenance: Literal["synthetic", "imported", "provider"]
    dataset_version: str


class ProviderPlan(Contract):
    id: str
    name: str
    region: str
    vcpu: int = Field(gt=0)
    memory_gib: float = Field(gt=0)
    disk_gib: float = Field(gt=0)
    compute_hourly_rate: Decimal = Field(ge=0)
    currency: Literal["INR"]
    billing_model: Literal["hourly"]
    pricing_source: Literal["illustrative", "provider"]
    catalog_version: str


class MetricSample(Contract):
    resource_id: str
    configuration_revision: int = Field(ge=1)
    timestamp: AwareDatetime
    cpu_used_cores: float | None = Field(default=None, ge=0)
    memory_used_gib: float | None = Field(default=None, ge=0)
    disk_used_gib: float | None = Field(default=None, ge=0)
    iops: float | None = Field(default=None, ge=0)
    network_in_mbps: float | None = Field(default=None, ge=0)
    network_out_mbps: float | None = Field(default=None, ge=0)
    dataset_version: str


class ErrorResponse(Contract):
    code: str
    message: str
    details: list[dict[str, object]] = Field(default_factory=list)
    request_id: str

