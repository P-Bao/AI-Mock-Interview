from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.career_kg import KGEnrichmentPayload


class Strength(BaseModel):
    area: str
    detail: str
    evidence: str


class Gap(BaseModel):
    area: str
    severity: Literal["critical", "moderate", "minor"]
    suggestion: str


class SkillsMatch(BaseModel):
    matched: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    missing_preferred: list[str] = Field(default_factory=list)


class ExperienceAssessment(BaseModel):
    years_required: int
    years_found: int
    relevance_score: int = Field(ge=0, le=100)
    notes: str


class CVQuality(BaseModel):
    clarity_score: int = Field(ge=0, le=100)
    ats_friendliness: int = Field(ge=0, le=100)
    improvement_tips: list[str] = Field(default_factory=list)


class CVAnalysisPayload(BaseModel):
    overall_match_score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[Strength] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    skills_match: SkillsMatch
    experience_assessment: ExperienceAssessment
    cv_quality: CVQuality
    recommended_interview_focus: list[str] = Field(default_factory=list)
    kg_enrichment: KGEnrichmentPayload | None = None


class CVAnalysisDocument(CVAnalysisPayload):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    session_id: str
    user_id: str | None = None
    filename: str
    job_title: str
    job_description: str
    target_language: Literal["en", "vi"] = "en"
    created_at: datetime
    model_used: str
    processing_time_ms: int
