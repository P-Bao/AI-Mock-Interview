import json
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.exceptions import SessionNotFoundException
from db.mongodb import get_db
from db.repositories.question_repo import QuestionRepository
from models.interview import AnswerUpdateRequest, JobQuestionGenerationRequest
from services.career_kg import build_job_kg_enrichment, enrich_questions_with_kg_metadata
from services.language_guard import (
    LanguageMismatchError,
    detect_target_language,
    validate_questions_language,
)
from services.question_gen import QuestionGenerationError, generate_job_interview_questions

router = APIRouter(tags=["questions"])


async def _set_status(redis_client, session_id: str, payload: dict) -> None:
    settings = get_settings()
    await redis_client.setex(
        f"questions:session:{session_id}",
        settings.task_ttl_seconds,
        json.dumps(payload),
    )


async def _process_job_questions(
    *,
    redis_client,
    session_id: str,
    job_title: str,
    job_description: str,
    experience_level: str,
    num_questions: int,
    user_id: str | None,
) -> None:
    started_at = time.perf_counter()
    target_language = detect_target_language(job_description)

    try:
        kg_enrichment = build_job_kg_enrichment(
            job_title=job_title,
            job_description=job_description,
            experience_level=experience_level,
        )
        questions = await generate_job_interview_questions(
            job_title=job_title,
            job_description=job_description,
            experience_level=experience_level,
            num_questions=num_questions,
            kg_enrichment=kg_enrichment,
            target_language=target_language,
        )
        enriched_questions = enrich_questions_with_kg_metadata(
            [q.model_dump() for q in questions.questions],
            kg_enrichment,
        )
        validate_questions_language(enriched_questions, target_language=target_language)
    except QuestionGenerationError as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "question_error", "detail": str(exc)})
        return
    except LanguageMismatchError as exc:
        await _set_status(
            redis_client,
            session_id,
            {"status": "failed", "reason": "language_mismatch", "detail": str(exc)},
        )
        return
    except Exception as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "unknown_error", "detail": str(exc)})
        return

    try:
        db = await get_db()
        repo = QuestionRepository(db)
        doc = {
            "session_id": session_id,
            "analysis_id": "",
            "source": "job_only",
            "user_id": user_id,
            "job_title": job_title,
            "job_description": job_description,
            "experience_level": experience_level,
            "target_language": target_language,
            "questions": enriched_questions,
            "total_questions": len(enriched_questions),
            "kg_enrichment": kg_enrichment.model_dump(),
            "processing_time_ms": int((time.perf_counter() - started_at) * 1000),
        }
        await repo.create(doc)
    except Exception as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "db_error", "detail": str(exc)})
        return

    await _set_status(redis_client, session_id, {"status": "done"})


@router.post("/questions/from-job", status_code=status.HTTP_202_ACCEPTED)
async def create_questions_from_job(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: JobQuestionGenerationRequest,
):
    settings = get_settings()
    if payload.num_questions > settings.max_questions:
        raise HTTPException(status_code=400, detail=f"num_questions must be between 1 and {settings.max_questions}")

    session_id = payload.session_id or str(uuid4())
    await _set_status(request.app.state.redis, session_id, {"status": "processing"})
    background_tasks.add_task(
        _process_job_questions,
        redis_client=request.app.state.redis,
        session_id=session_id,
        job_title=payload.job_title,
        job_description=payload.job_description,
        experience_level=payload.experience_level,
        num_questions=payload.num_questions,
        user_id=payload.user_id,
    )
    return {
        "session_id": session_id,
        "question_session_id": session_id,
        "status": "processing",
        "source": "job_only",
    }


@router.get("/questions/{session_id}")
async def get_questions(request: Request, session_id: str):
    db = await get_db()
    repo = QuestionRepository(db)
    doc = await repo.get_by_session_id(session_id)
    if doc is not None:
        return doc

    status_payload = await request.app.state.redis.get(f"cv:session:{session_id}")
    if not status_payload:
        status_payload = await request.app.state.redis.get(f"questions:session:{session_id}")
    if status_payload:
        status_data = json.loads(status_payload)
        if status_data.get("status") == "processing":
            return JSONResponse(status_code=202, content={"status": "processing"})
        if status_data.get("status") == "failed":
            return JSONResponse(status_code=500, content=status_data)

    raise SessionNotFoundException()


@router.patch("/questions/{session_id}/{question_index}/answer")
async def update_question_answer(session_id: str, question_index: int, payload: AnswerUpdateRequest):
    if question_index < 0:
        raise HTTPException(status_code=400, detail="question_index must be >= 0")

    db = await get_db()
    repo = QuestionRepository(db)

    existing = await repo.get_by_session_id(session_id)
    if existing is None:
        raise SessionNotFoundException()
    if question_index >= len(existing.get("questions", [])):
        raise HTTPException(status_code=404, detail="Question index out of range")

    updated = await repo.update_answer(
        session_id=session_id,
        question_index=question_index,
        answer_given=payload.answer_given,
        answer_score=payload.answer_score,
    )
    return updated
