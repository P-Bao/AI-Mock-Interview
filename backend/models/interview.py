from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.career_kg import KGEnrichmentPayload


class Question(BaseModel):
    question: str
    type: Literal["technical", "behavioral", "situational"]
    difficulty: Literal["easy", "medium", "hard"]
    target_skill: str
    why_asked: str
    answered: bool = False
    answer_given: str | None = None
    answer_score: int | None = Field(default=None, ge=0, le=100)
    kg_requirement: str | None = None
    kg_match_score: float | None = Field(default=None, ge=0, le=1)
    kg_gap_severity: Literal["critical", "moderate", "minor"] | None = None
    kg_priority: float | None = Field(default=None, ge=0, le=1)


class InterviewQuestionsPayload(BaseModel):
    questions: list[Question] = Field(default_factory=list)


class JobQuestionGenerationRequest(BaseModel):
    job_title: str
    job_description: str
    experience_level: Literal["intern", "fresher", "junior", "mid", "senior", "lead"]
    num_questions: int = Field(default=10, ge=1)
    session_id: str | None = None
    user_id: str | None = None


class InterviewQuestionsDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    session_id: str
    analysis_id: str
    job_title: str
    job_description: str = ""
    experience_level: Literal["intern", "fresher", "junior", "mid", "senior", "lead"]
    target_language: Literal["en", "vi"] = "en"
    questions: list[Question]
    total_questions: int
    created_at: datetime
    kg_enrichment: KGEnrichmentPayload | None = None


class AnswerUpdateRequest(BaseModel):
    answer_given: str
    answer_score: int | None = Field(default=None, ge=0, le=100)
