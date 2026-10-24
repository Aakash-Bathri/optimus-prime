from decimal import Decimal
from typing import Any, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

T = TypeVar("T")
Decision = Literal["pending", "accepted", "rejected"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Page(Contract, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class Resource(Contract):
    id: str
    name: str
    type: Literal["vm", "block_volume", "public_ip", "gpu"]
    region: str
    environment: Literal["production", "staging", "development"]
    team: str | None = None
    owner: str | None = None
    current_plan_id: str | None = None
    configuration_revision: int = Field(default=1, ge=1)
    provenance: Literal["synthetic"] = "synthetic"
    dataset_version: str
    status: str
    hardware: str | None = None
    instance_family: str | None = None
    vcpu: int | None = Field(default=None, gt=0)
    memory_gib: float | None = Field(default=None, gt=0)
    disk_gb: float | None = Field(default=None, gt=0)
    storage_type: str | None = None
    transfer_allowance_gb: float | None = Field(default=None, ge=0)
    criticality: str
    created_at: AwareDatetime
    attached_to: str | None = None
    lifecycle_state: str
    gpu_model: str | None = None
    gpu_vram_gib: float | None = Field(default=None, gt=0)
    gpu_workload: str | None = None
    monthly_cost: Decimal | None = Field(default=None, ge=0)
    cost_basis: str | None = None
    cpu_p95: float | None = None
    memory_p95: float | None = None
    coverage: float | None = None


class ProviderPlan(Contract):
    id: str
    name: str
    hardware: str
    instance_family: str
    region: str | None = None
    vcpu: int = Field(gt=0)
    memory_gib: float = Field(gt=0)
    disk_gb: float | None = Field(default=None, gt=0)
    storage_type: str
    transfer_allowance_gb: float | None = Field(default=None, ge=0)
    compute_hourly_rate: Decimal = Field(ge=0)
    compute_quarterly_rate: Decimal = Field(ge=0)
    compute_monthly_equivalent: Decimal = Field(ge=0)
    currency: Literal["INR"] = "INR"
    billing_model: Literal["quarterly_monthly_equivalent"] = "quarterly_monthly_equivalent"
    pricing_source: str
    catalog_version: str
    region_verified: bool = False
    pricing_verified: bool = False
    resize_verified: bool = False
    storage_verified: bool = False
    iops_limit: float | None = Field(default=None, gt=0)
    network_mbps_limit: float | None = Field(default=None, gt=0)


class MetricSample(Contract):
    resource_id: str
    timestamp: AwareDatetime
    cpu: float | None = Field(default=None, ge=0, le=100)
    memory: float | None = Field(default=None, ge=0, le=100)
    disk: float | None = Field(default=None, ge=0, le=100)
    iops: float | None = Field(default=None, ge=0)
    network_in: float | None = Field(default=None, ge=0)
    network_out: float | None = Field(default=None, ge=0)
    quality_flag: str


class MetricStatistics(Contract):
    count: int
    mean: float
    minimum: float
    p50: float
    p95: float
    p99: float
    maximum: float
    ewma: float
    mad_outlier_count: int
    unit: str


class DataQuality(Contract):
    expected_samples: int
    observed_samples: int
    valid_samples: int
    coverage: float
    metric_coverage: dict[str, float]
    latest_sample: AwareDatetime | None
    freshness_seconds: float | None
    window_start: AwareDatetime
    window_end: AwareDatetime
    sufficient: bool
    warnings: list[str]


class Analysis(Contract):
    resource_id: str
    quality: DataQuality
    statistics: dict[str, MetricStatistics]


class Check(Contract):
    code: str
    status: Literal["passed", "failed", "unknown"]
    message: str
    actual: float | str | None = None
    limit: float | str | None = None
    unit: str | None = None


class Replay(Contract):
    sample_count: int
    missing_samples: int
    cpu_breaches: int
    memory_breaches: int
    breached_samples: int
    longest_breach_samples: int
    stress_breached_samples: int
    stress_multiplier: float
    mode: Literal["historical_capacity_projection"] = "historical_capacity_projection"


class CandidateEvaluation(Contract):
    plan: ProviderPlan
    checks: list[Check]
    capacity_eligible: bool
    eligible: bool
    monthly_cost: Decimal
    monthly_savings: Decimal | None
    projected_cpu_p99: float | None
    projected_cpu_peak: float | None
    projected_memory_p99: float | None
    projected_memory_peak: float | None
    replay: Replay | None = None


class Provenance(Contract):
    dataset_version: str
    catalog_version: str
    policy_version: str
    engine_version: str
    analysis_as_of: AwareDatetime
    mode: Literal["historical_synthetic_snapshot"] = "historical_synthetic_snapshot"
    pricing_source: str
    assumptions: list[str]


class RecommendationSummary(Contract):
    id: str
    version: str
    resource_id: str
    resource_name: str
    environment: str
    region: str
    team: str | None
    action: Literal["resize", "capacity_review", "idle_review", "orphan_review", "observe"]
    outcome: Literal["recommendation", "blocked", "insufficient_data", "no_action", "unsupported"]
    title: str
    explanation: str
    risk: Literal["low", "moderate", "high", "unknown"]
    ready: bool
    review_only: bool
    current_plan_id: str | None
    target_plan_id: str | None
    current_monthly_cost: Decimal | None
    target_monthly_cost: Decimal | None
    modeled_monthly_savings: Decimal | None
    conditional_monthly_savings: Decimal | None
    blockers: list[str]
    prerequisites: list[str]
    decision: Decision = "pending"
    decision_revision: int = 0
    decided_at: AwareDatetime | None = None


class Recommendation(RecommendationSummary):
    analysis: Analysis | None = None
    candidates: list[CandidateEvaluation] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    provenance: Provenance


class DecisionRequest(Contract):
    decision: Decision
    version: str
    expected_revision: int = Field(ge=0)


class SimulationRequest(Contract):
    resource_id: str
    target_plan_id: str
    demand_multiplier: float = Field(default=1, ge=0.5, le=3)


class Alert(Contract):
    id: str
    resource_id: str | None = None
    resource_name: str | None = None
    category: Literal["usage_anomaly", "capacity_pressure", "data_quality", "cost_increase"]
    severity: Literal["info", "warning", "critical"]
    title: str
    explanation: str
    timestamp: AwareDatetime
    observed: float
    baseline: float
    threshold: float
    unit: str
    source: Literal["synthetic_telemetry", "synthetic_billing"]


class ErrorResponse(Contract):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    request_id: str

