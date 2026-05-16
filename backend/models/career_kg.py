from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequirementCluster(BaseModel):
    name: str
    weight: float = Field(ge=0, le=1)
    requirements: list[str] = Field(default_factory=list)
    evidence_source: str | None = None
    evidence: list[str] = Field(default_factory=list)


class SkillMatch(BaseModel):
    requirement: str
    cv_skill: str
    score: float = Field(ge=0, le=1)
    relation: Literal["exact", "related", "missing", "unknown"]
    evidence_source: str | None = None
    evidence: list[str] = Field(default_factory=list)


class SkillGap(BaseModel):
    skill: str
    severity: Literal["critical", "moderate", "minor"]
    reason: str
    recommendation: str
    priority: float = Field(default=0.0, ge=0, le=1)
    evidence_source: str | None = None
    evidence: list[str] = Field(default_factory=list)


class QuestionTarget(BaseModel):
    requirement: str
    skill: str
    priority: float = Field(ge=0, le=1)
    difficulty: Literal["easy", "medium", "hard"]
    why_asked: str
    gap_severity: Literal["critical", "moderate", "minor"] | None = None
    evidence: list[str] = Field(default_factory=list)


class CareerGuidance(BaseModel):
    target_role: str
    path: list[str] = Field(default_factory=list)
    path_probability: float = Field(ge=0, le=1)
    recommendations: list[str] = Field(default_factory=list)


class KGEnrichmentPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = True
    source: str = "Tinix-CareerPathKG"
    version: str = "heuristic"
    requirement_clusters: list[RequirementCluster] = Field(default_factory=list)
    skill_matches: list[SkillMatch] = Field(default_factory=list)
    skill_gaps: list[SkillGap] = Field(default_factory=list)
    question_targets: list[QuestionTarget] = Field(default_factory=list)
    career_guidance: CareerGuidance | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    processing_time_ms: int = 0
    error: str | None = None
