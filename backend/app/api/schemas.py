from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator

class ExperimentRequest(BaseModel):
    source_profile: str = Field(min_length=1, max_length=512)
    target_profile: str = Field(min_length=1, max_length=512)
    version_id: str | None = Field(default=None, min_length=64, max_length=64)
    minimum_prerequisite_level: float = Field(default=1, ge=0, le=4, allow_inf_nan=False)
    lambda_: float = Field(default=0.5, alias="lambda", ge=0, le=10, allow_inf_nan=False)
    algorithm: Literal["kahn", "dfs"] = "kahn"
    weight_source: Literal["role_skill_weights.csv", "skill_weights_by_role_final_v2.csv"] = "skill_weights_by_role_final_v2.csv"
    included_edges: list[tuple[str, str]] = Field(default_factory=list, max_length=10000)
    excluded_edges: list[tuple[str, str]] = Field(default_factory=list, max_length=10000)
    verification_scope: Literal["all", "verified"] = "all"
    graph_configuration: Literal["G1", "G2", "G3"] | None = None
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

VerificationStatus = Literal["Unverified", "Expert Verified", "Source Verified"]
Entity = Literal["requirement", "prerequisite", "weight", "course_skill", "skill", "group", "membership", "level", "survey_mapping", "dependency_count", "profile", "source_row"]

class Verification(BaseModel):
    status: VerificationStatus = "Unverified"
    reviewer: str | None = Field(default=None, max_length=300)
    evidence: str | None = Field(default=None, max_length=5000)
    note: str | None = Field(default=None, max_length=5000)
    model_config = ConfigDict(extra="forbid")

class RecordChange(BaseModel):
    entity: Entity
    key: list[str] = Field(min_length=1, max_length=4)
    operation: Literal["upsert", "delete", "verify"]
    required_level: float | None = Field(default=None, ge=0, le=4, allow_inf_nan=False)
    verification: Verification = Field(default_factory=Verification)
    model_config = ConfigDict(extra="forbid")

class RevisionRequest(BaseModel):
    parent_id: str = Field(min_length=64, max_length=64)
    label: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1, max_length=5000)
    changes: list[RecordChange] = Field(min_length=1, max_length=500)
    model_config = ConfigDict(extra="forbid")

class VersionComparisonRequest(BaseModel):
    original_version: str = Field(min_length=64, max_length=64)
    corrected_version: str = Field(min_length=64, max_length=64)
    experiment: ExperimentRequest
    batch: bool = False
    model_config = ConfigDict(extra="forbid")

class ResearchRequest(BaseModel):
    experiment: ExperimentRequest
    taus: list[float] = Field(default_factory=lambda: [1., 2., 3.], min_length=1, max_length=7)
    lambdas: list[float] = Field(default_factory=lambda: [0., .5, 1.], min_length=1, max_length=7)
    top_k: Literal[3, 5] = 3
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def valid_grid(self):
        import math
        if any(not math.isfinite(x) or x < 0 or x > 4 for x in self.taus):
            raise ValueError("tau must be finite and in 0..4")
        if any(not math.isfinite(x) or x < 0 or x > 10 for x in self.lambdas):
            raise ValueError("lambda must be finite and in 0..10")
        if len(set(self.taus)) != len(self.taus) or len(set(self.lambdas)) != len(self.lambdas):
            raise ValueError("Duplicate grid coordinates are not allowed")
        if len(self.taus) * len(self.lambdas) > 25:
            raise ValueError("At most 25 sensitivity scenarios per request")
        self.taus, self.lambdas = sorted(self.taus), sorted(self.lambdas)
        return self


class RelationImpactRequest(BaseModel):
    experiment: ExperimentRequest
    taus: list[float] = Field(default_factory=lambda: [1., 2., 3.], min_length=1, max_length=7)
    lambdas: list[float] = Field(default_factory=lambda: [0., .5, 1.], min_length=1, max_length=7)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def controlled_graphs(self):
        # This new study always evaluates BOTH Top-3 and Top-5; it does not
        # inherit or silently reinterpret ResearchRequest.top_k.
        grid = ResearchRequest(experiment=self.experiment, taus=self.taus, lambdas=self.lambdas)
        self.taus, self.lambdas = grid.taus, grid.lambdas
        if self.experiment.graph_configuration is not None:
            raise ValueError("The controlled comparison selects all three graphs; omit experiment.graph_configuration")
        if self.experiment.included_edges or self.experiment.excluded_edges:
            raise ValueError("G1/G2/G3 comparison does not allow additional edge overrides")
        if self.experiment.verification_scope != "all":
            raise ValueError("Preliminary Unverified classifications require verification_scope=all")
        return self

class Experiment2Request(BaseModel):
    """Version is selectable; all scientific controls belong to the fixed protocol."""
    version_id: str = Field(min_length=64, max_length=64)
    model_config = ConfigDict(extra="forbid")

class Experiment3Request(BaseModel):
    version_id: str = Field(min_length=64, max_length=64)
    model_config = ConfigDict(extra='forbid')
