from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.career_kg import KGEnrichmentPayload


class TranscriptEntry(BaseModel):
    role: Literal["user", "model"]
    text: str


class EvaluationRequest(BaseModel):
    interview: list[TranscriptEntry]
    session_id: str | None = None
    user_id: str | None = None
    interview_session_id: str | None = None
    question_session_id: str | None = None
    cv_session_id: str | None = None
    target_language: Literal["en", "vi"] | None = None


class STARScores(BaseModel):
    situation: int = Field(ge=0, le=10)
    task: int = Field(ge=0, le=10)
    action: int = Field(ge=0, le=10)
    result: int = Field(ge=0, le=10)


class QuestionEvaluation(BaseModel):
    question_index: int
    question_text: str = ""
    answer_text: str = ""
    star_scores: STARScores
    question_score: float = Field(ge=0, le=10)
    comment: str


class OverallEvaluation(BaseModel):
    overall_score: float = Field(ge=0, le=10)
    strengths: list[str] = Field(default_factory=list)
    key_improvements: list[str] = Field(default_factory=list)
    overall_comment: str


class EvaluationPayload(BaseModel):
    questions: list[QuestionEvaluation] = Field(default_factory=list)
    overall: OverallEvaluation


class EvaluationDocument(EvaluationPayload):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    session_id: str
    user_id: str | None = None
    interview_session_id: str | None = None
    question_session_id: str | None = None
    cv_session_id: str | None = None
    target_language: Literal["en", "vi"] = "en"
    transcript: list[TranscriptEntry]
    total_questions: int
    kg_context_used: bool = False
    kg_enrichment: KGEnrichmentPayload | None = None
    created_at: datetime
    model_used: str
    processing_time_ms: int
