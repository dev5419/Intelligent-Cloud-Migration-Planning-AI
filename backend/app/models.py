from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SixRStrategy = Literal[
    "Rehost",
    "Replatform",
    "Repurchase",
    "Refactor",
    "Retire",
    "Retain",
]


class Application(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    application_id: str | None = None
    name: str
    application_name: str | None = None
    owner: str | None = None
    technology: str | None = None
    criticality: Literal["Low", "Medium", "High"]
    dependencies: list[str] = Field(default_factory=list)
    cpu_usage: float | None = None
    memory_usage: float | None = None
    age_years: int | None = None
    compliance_flag: int | None = None
    dependency_ids: list[str] = Field(default_factory=list)
    dependency_count: int = 0

    @model_validator(mode="after")
    def sync_fields(self):
        if self.application_id is None:
            self.application_id = self.id
        if self.application_name is None:
            self.application_name = self.name
        if not self.dependencies and self.dependency_ids:
            self.dependencies = self.dependency_ids
        if self.id != self.application_id and self.application_id:
            self.id = self.application_id
        return self


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    app_id: str | None = None
    application_id: str | None = None

    @model_validator(mode="after")
    def ensure_identifier(self):
        value = (self.app_id or self.application_id or "").strip()
        if not value:
            raise ValueError("Either 'app_id' or 'application_id' must be provided.")
        self.app_id = value
        self.application_id = value
        return self


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    app_id: str
    application_id: str
    recommendation: SixRStrategy
    confidence: float = Field(ge=0, le=1)
    explanation: dict[str, Any] | str


class MigrationWavesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    application_ids: list[str] | None = None


class MigrationWave(BaseModel):
    wave: int = Field(ge=1)
    applications: list[str]
    risk: Literal["Low", "Medium", "High"]
    risk_score: float = 0
    application_count: int = 0
    unmet_dependencies: int = 0
    depends_on_waves: list[int] = Field(default_factory=list)
    cycle_break: bool = False
    clusters: list[dict[str, Any]] = Field(default_factory=list)


class MigrationWavesResponse(BaseModel):
    waves: list[MigrationWave]
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class CopilotRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    question: str = Field(min_length=1, max_length=1000)


class CopilotResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]


class CostRiskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    app_id: str | None = None
    application_id: str | None = None

    @model_validator(mode="after")
    def ensure_identifier(self):
        value = (self.app_id or self.application_id or "").strip()
        if not value:
            raise ValueError("Either 'app_id' or 'application_id' must be provided.")
        self.app_id = value
        self.application_id = value
        return self


class CostRiskResponse(BaseModel):
    app_id: str
    application_id: str
    monthly_aws_cost: float = Field(ge=0)
    cost_range: dict[str, float]
    risk_score: float = Field(ge=0, le=100)
