import asyncio
import json
from typing import Any

import httpx
from pydantic import ValidationError

from core.config import get_settings
from models.career_kg import KGEnrichmentPayload
from models.cv_analysis import CVAnalysisPayload
from models.interview import InterviewQuestionsPayload
from prompts.question_gen import QUESTION_GEN_SYSTEM_PROMPT_TEMPLATE, build_question_gen_user_prompt


class QuestionGenerationError(Exception):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")

    return json.loads(stripped[start : end + 1])


async def _call_gemini(system_prompt: str, user_prompt: str, timeout_seconds: int) -> str:
    settings = get_settings()
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "text/plain",
        },
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise QuestionGenerationError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise QuestionGenerationError("Gemini returned empty content")
    return text


def _summarize_strengths(analysis: CVAnalysisPayload) -> str:
    return "; ".join([f"{x.area}: {x.detail}" for x in analysis.strengths])


def _summarize_gaps(analysis: CVAnalysisPayload) -> str:
    return "; ".join([f"{x.area} ({x.severity})" for x in analysis.gaps])


def _summarize_kg_context(kg_enrichment: KGEnrichmentPayload | None) -> str:
    if kg_enrichment is None or not kg_enrichment.enabled:
        return "disabled"

    top_gaps = ", ".join([gap.skill for gap in kg_enrichment.skill_gaps[:5]]) or "none"
    top_matches = ", ".join([match.requirement for match in kg_enrichment.skill_matches[:5]]) or "none"
    guidance = ", ".join(kg_enrichment.career_guidance.recommendations[:3]) if kg_enrichment.career_guidance else "none"
    return (
        f"mode={kg_enrichment.version}; "
        f"confidence={kg_enrichment.confidence:.2f}; "
        f"top_gaps={top_gaps}; "
        f"top_matches={top_matches}; "
        f"guidance={guidance}"
    )


def _summarize_question_targets(kg_enrichment: KGEnrichmentPayload | None, *, limit: int = 8) -> str:
    if kg_enrichment is None or not kg_enrichment.enabled or not kg_enrichment.question_targets:
        return ""

    lines = []
    for target in kg_enrichment.question_targets[:limit]:
        lines.append(
            " | ".join(
                [
                    f"requirement={target.requirement}",
                    f"skill={target.skill}",
                    f"priority={target.priority:.2f}",
                    f"difficulty={target.difficulty}",
                    f"why={target.why_asked}",
                ]
            )
        )
    return "\n".join(lines)


async def generate_interview_questions(
    *,
    analysis: CVAnalysisPayload,
    job_title: str,
    experience_level: str,
    num_questions: int,
    kg_enrichment: KGEnrichmentPayload | None = None,
    target_language: str = "en",
) -> InterviewQuestionsPayload:
    system_prompt = QUESTION_GEN_SYSTEM_PROMPT_TEMPLATE.format(num_questions=num_questions)
    effective_kg = kg_enrichment or analysis.kg_enrichment
    question_targets = _summarize_question_targets(effective_kg)
    user_prompt = build_question_gen_user_prompt(
        job_title=job_title,
        experience_level=experience_level,
        strengths_summary=_summarize_strengths(analysis),
        gaps_summary=_summarize_gaps(analysis),
        recommended_focus=question_targets or ", ".join(analysis.recommended_interview_focus),
        matched_skills=", ".join(analysis.skills_match.matched),
        missing_required=", ".join(analysis.skills_match.missing_required),
        kg_context=_summarize_kg_context(effective_kg),
        target_language=target_language,
    )

    last_error: Exception | None = None
    repair_instruction = (
        f"Return only valid JSON and include exactly {num_questions} questions. "
        "Do not include markdown or any explanation."
    )

    for attempt in range(3):
        try:
            prompt = user_prompt if attempt == 0 else f"{user_prompt}\n\n{repair_instruction}"
            raw = await _call_gemini(system_prompt, prompt, timeout_seconds=20)
            data = _extract_json(raw)
            payload = InterviewQuestionsPayload.model_validate(data)
            if len(payload.questions) != num_questions:
                raise ValueError("Incorrect number of questions returned")
            return payload
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise QuestionGenerationError("Gemini timeout while generating questions") from exc
        except httpx.HTTPStatusError as exc:
            raise QuestionGenerationError(f"Gemini HTTP error: {exc.response.status_code}") from exc
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            continue
        except Exception as exc:
            raise QuestionGenerationError("Failed to generate interview questions") from exc

    raise QuestionGenerationError(f"Gemini returned invalid question JSON after retries: {last_error}")


async def generate_job_interview_questions(
    *,
    job_title: str,
    job_description: str,
    experience_level: str,
    num_questions: int,
    kg_enrichment: KGEnrichmentPayload | None = None,
    target_language: str = "en",
) -> InterviewQuestionsPayload:
    system_prompt = QUESTION_GEN_SYSTEM_PROMPT_TEMPLATE.format(num_questions=num_questions)
    missing_required = ", ".join([gap.skill for gap in (kg_enrichment.skill_gaps if kg_enrichment else [])])
    question_targets = _summarize_question_targets(kg_enrichment)
    user_prompt = build_question_gen_user_prompt(
        job_title=job_title,
        job_description=job_description,
        experience_level=experience_level,
        strengths_summary="No CV provided. Generate role-based screening questions from the job description.",
        gaps_summary="No candidate evidence yet. Treat job requirements as areas to verify during interview.",
        recommended_focus=question_targets or missing_required or job_description,
        matched_skills="none",
        missing_required=missing_required or job_description,
        kg_context=_summarize_kg_context(kg_enrichment),
        target_language=target_language,
    )

    last_error: Exception | None = None
    repair_instruction = (
        f"Return only valid JSON and include exactly {num_questions} questions. "
        "Do not include markdown or any explanation."
    )

    for attempt in range(3):
        try:
            prompt = user_prompt if attempt == 0 else f"{user_prompt}\n\n{repair_instruction}"
            raw = await _call_gemini(system_prompt, prompt, timeout_seconds=20)
            data = _extract_json(raw)
            payload = InterviewQuestionsPayload.model_validate(data)
            if len(payload.questions) != num_questions:
                raise ValueError("Incorrect number of questions returned")
            return payload
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise QuestionGenerationError("Gemini timeout while generating job-only questions") from exc
        except httpx.HTTPStatusError as exc:
            raise QuestionGenerationError(f"Gemini HTTP error: {exc.response.status_code}") from exc
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            continue
        except Exception as exc:
            raise QuestionGenerationError("Failed to generate job-only questions") from exc

    raise QuestionGenerationError(f"Gemini returned invalid job-only question JSON after retries: {last_error}")
