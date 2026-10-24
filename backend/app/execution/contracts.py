"""Person 5's handoff contracts. Evidence comes from the engine, never the LLM."""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.models.contracts import Contract

INSTANCE_TYPES = ("m5.large", "m5.xlarge", "m5.2xlarge")
LAB_CAPACITIES = {"m5.large": (2, 8), "m5.xlarge": (4, 16), "m5.2xlarge": (8, 32)}


class EngineReference(Contract):
    recommendation_id: str
    recommendation_version: str
    decision_revision: int = Field(ge=1)
    source_resource_id: str
    target_plan_id: str
    analysis_as_of: AwareDatetime
    provider_blockers: list[str]


class EnginePrepareRequest(Contract):
    recommendation_id: str
    target_plan_id: str
    binding_resource_id: str
    mode: Literal["llm", "scripted"] = "llm"


class Binding(Contract):
    resource_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    provider_id: str = Field(pattern=r"^i-[a-f0-9]{8,32}$")
    management: Literal["terraform", "manual"]
    repository: str | None = Field(default=None, pattern=r"^[\w.-]+/[\w.-]+$")
    terraform_address: str | None = None
    variables_file: str | None = None
    variable: str | None = None

    @model_validator(mode="after")
    def mapping(self):
        fields = (self.repository, self.terraform_address, self.variables_file, self.variable)
        if self.management == "terraform" and not all(fields):
            raise ValueError("Terraform resources require the repository and exact file/variable mapping")
        if self.management == "manual" and any(fields):
            raise ValueError("Manual resources cannot have Terraform mappings")
        if self.variables_file and (
            not self.variables_file.endswith(".tfvars.json")
            or any(part in ("", ".", "..") for part in self.variables_file.split("/"))
            or "\\" in self.variables_file or ":" in self.variables_file
        ):
            raise ValueError("Use a repository-relative .tfvars.json path")
        return self


class Evidence(Contract):
    version: str = Field(min_length=1, max_length=100)
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    checks_passed: bool
    source: Literal["stub", "engine", "engine_lab"]
    engine_reference: EngineReference | None = None
    reason: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def window(self):
        if self.expires_at <= self.observed_at:
            raise ValueError("Evidence expiry must follow observation")
        return self


class Recommendation(Contract):
    id: str = Field(min_length=1, max_length=100)
    resource_id: str
    action: Literal["resize", "stop", "start"]
    target_instance_type: Literal["m5.large", "m5.xlarge", "m5.2xlarge"] | None = None
    evidence: Evidence

    @model_validator(mode="after")
    def target(self):
        if (self.action == "resize") != (self.target_instance_type is not None):
            raise ValueError("Only resize requires a target instance type")
        return self


class PrepareRequest(Contract):
    recommendation: Recommendation
    mode: Literal["llm", "scripted"] = "llm"


class Decision(Contract):
    digest: str
    decision: Literal["approve", "reject"]


class ExecuteRequest(Contract):
    digest: str


class WorkflowError(Exception):
    def __init__(self, message: str, status: int = 409):
        super().__init__(message)
        self.status = status


def utcnow():
    from datetime import timezone
    return datetime.now(timezone.utc)
