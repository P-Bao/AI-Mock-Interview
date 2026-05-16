import json
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.exceptions import InvalidTranscriptException, SessionNotFoundException
from db.mongodb import get_db
from db.repositories.evaluation_repo import EvaluationRepository
from models.evaluation import EvaluationRequest
from services.evaluation_kg import load_evaluation_context_info
from services.evaluator import EvaluationError, evaluate_interview
from services.language_guard import (
    build_language_mismatch_evaluation,
    detect_target_language,
    find_transcript_language_mismatch,
)

router = APIRouter(tags=["evaluation"])


def _has_user_answer(interview: list[dict[str, str]]) -> bool:
    return any(item.get("role") == "user" and (item.get("text") or "").strip() for item in interview)


async def _set_status(redis_client, session_id: str, payload: dict) -> None:
    settings = get_settings()
    await redis_client.setex(
        f"evaluation:session:{session_id}",
        settings.task_ttl_seconds,
        json.dumps(payload),
    )


async def _process_evaluation(
    *,
    redis_client,
    session_id: str,
    interview: list[dict[str, str]],
    user_id: str | None,
    interview_session_id: str | None,
    question_session_id: str | None,
    cv_session_id: str | None,
    target_language: str | None,
) -> None:
    started_at = time.perf_counter()
    settings = get_settings()
    kg_context = None
    kg_enrichment = None
    language_policy_failed = False
    effective_question_session_id = question_session_id or cv_session_id

    try:
        kg_context, kg_enrichment, session_target_language = await load_evaluation_context_info(
            effective_question_session_id
        )
        effective_target_language = (
            target_language
            if target_language in {"en", "vi"}
            else session_target_language or detect_target_language(" ".join(item["text"] for item in interview))
        )
        mismatch = find_transcript_language_mismatch(interview, target_language=effective_target_language)
        if mismatch:
            language_policy_failed = True
            evaluation_payload = build_language_mismatch_evaluation(
                interview,
                target_language=effective_target_language,
                mismatch=mismatch,
            )
        else:
            evaluation_payload = await evaluate_interview(
                transcript=interview,
                kg_context=kg_context,
                target_language=effective_target_language,
                timeout_seconds=settings.eval_timeout_seconds,
            )
    except EvaluationError as exc:
        await _set_status(
            redis_client,
            session_id,
            {"status": "failed", "reason": "evaluation_error", "detail": str(exc)},
        )
        return
    except Exception as exc:
        await _set_status(
            redis_client,
            session_id,
            {"status": "failed", "reason": "unknown_error", "detail": str(exc)},
        )
        return

    try:
        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        db = await get_db()
        repo = EvaluationRepository(db)

        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "interview_session_id": interview_session_id,
            "question_session_id": effective_question_session_id,
            "cv_session_id": cv_session_id,
            "target_language": effective_target_language,
            "transcript": interview,
            **evaluation_payload.model_dump(),
            "total_questions": len(evaluation_payload.questions),
            "kg_context_used": bool(kg_context),
            "kg_enrichment": kg_enrichment,
            "language_policy_failed": language_policy_failed,
            "model_used": settings.gemini_model,
            "processing_time_ms": processing_time_ms,
        }
        await repo.create(doc)
    except Exception as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "db_error", "detail": str(exc)})
        return

    await _set_status(redis_client, session_id, {"status": "done"})


@router.post("/evaluations", status_code=status.HTTP_202_ACCEPTED)
async def create_evaluation(request: Request, background_tasks: BackgroundTasks, payload: EvaluationRequest):
    interview = [entry.model_dump() for entry in payload.interview]
    if not interview or not _has_user_answer(interview):
        raise InvalidTranscriptException()

    session_id = payload.session_id or str(uuid4())
    await _set_status(request.app.state.redis, session_id, {"status": "processing"})
    background_tasks.add_task(
        _process_evaluation,
        redis_client=request.app.state.redis,
        session_id=session_id,
        interview=interview,
        user_id=payload.user_id,
        interview_session_id=payload.interview_session_id,
        question_session_id=payload.question_session_id,
        cv_session_id=payload.cv_session_id,
        target_language=payload.target_language,
    )
    return {"session_id": session_id, "status": "processing"}


@router.get("/evaluations/history/{user_id}")
async def get_evaluation_history(user_id: str, page: int = 1, limit: int = 10):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="page and limit must be positive")

    db = await get_db()
    repo = EvaluationRepository(db)
    return await repo.list_history_by_user(user_id=user_id, page=page, limit=limit)


@router.get("/evaluations/by-interview/{interview_session_id}")
async def get_evaluation_by_interview(interview_session_id: str):
    db = await get_db()
    repo = EvaluationRepository(db)
    doc = await repo.get_by_interview_session_id(interview_session_id)
    if doc is None:
        raise SessionNotFoundException()
    return doc


@router.get("/evaluations/{session_id}")
async def get_evaluation(request: Request, session_id: str):
    db = await get_db()
    repo = EvaluationRepository(db)
    doc = await repo.get_by_session_id(session_id)
    if doc is not None:
        return doc

    status_payload = await request.app.state.redis.get(f"evaluation:session:{session_id}")
    if status_payload:
        status_data = json.loads(status_payload)
        if status_data.get("status") == "processing":
            return JSONResponse(status_code=202, content={"status": "processing"})
        if status_data.get("status") == "failed":
            return JSONResponse(status_code=500, content=status_data)

    raise SessionNotFoundException()
