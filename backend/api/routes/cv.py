import asyncio
import json
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.exceptions import FileTooLargeException, InvalidFileTypeException, SessionNotFoundException
from db.mongodb import get_db
from db.repositories.cv_repo import CVRepository
from db.repositories.question_repo import QuestionRepository
from models.career_kg import KGEnrichmentPayload
from services.analyzer import CVAnalyzerError, analyze_cv
from services.career_kg import build_career_kg_enrichment, enrich_questions_with_kg_metadata
from services.language_guard import (
    LanguageMismatchError,
    detect_target_language,
    validate_questions_language,
    validate_text_language,
)
from services.parser import ResumeParseError, parse_resume_to_markdown
from services.question_gen import QuestionGenerationError, generate_interview_questions

router = APIRouter(tags=["cv"])


def _validate_upload(file: UploadFile, size_bytes: int) -> None:
    settings = get_settings()
    ext = (file.filename or "").lower()
    if not (ext.endswith(".pdf") or ext.endswith(".docx")):
        raise InvalidFileTypeException()

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileTooLargeException(settings.max_file_size_mb)


async def _set_status(redis_client, session_id: str, payload: dict) -> None:
    settings = get_settings()
    await redis_client.setex(
        f"cv:session:{session_id}",
        settings.task_ttl_seconds,
        json.dumps(payload),
    )


async def _process_pipeline(
    *,
    redis_client,
    session_id: str,
    file_name: str,
    file_bytes: bytes,
    job_title: str,
    job_description: str,
    experience_level: str,
    num_questions: int,
    user_id: str | None,
) -> None:
    started_at = time.perf_counter()
    target_language = detect_target_language(job_description)

    try:
        settings = get_settings()
        cv_markdown = await asyncio.wait_for(
            parse_resume_to_markdown(file_bytes, file_name),
            timeout=settings.mineru_timeout_seconds + 30,
        )
    except ResumeParseError as exc:
        reason = "parser_timeout" if "timed out" in str(exc).lower() else "parse_error"
        await _set_status(redis_client, session_id, {"status": "failed", "reason": reason, "detail": str(exc)})
        return
    except asyncio.TimeoutError as exc:
        await _set_status(
            redis_client,
            session_id,
            {"status": "failed", "reason": "parser_timeout", "detail": "Parser exceeded background timeout"},
        )
        return
    except Exception as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "parse_error", "detail": str(exc)})
        return

    try:
        validate_text_language(cv_markdown, target_language=target_language, field="cv_markdown")
    except LanguageMismatchError as exc:
        await _set_status(
            redis_client,
            session_id,
            {"status": "failed", "reason": "language_mismatch", "detail": str(exc)},
        )
        return

    try:
        analysis = await analyze_cv(
            cv_markdown=cv_markdown,
            job_title=job_title,
            job_description=job_description,
            experience_level=experience_level,
            target_language=target_language,
        )
    except CVAnalyzerError as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "analysis_error", "detail": str(exc)})
        return

    try:
        kg_enrichment: KGEnrichmentPayload = await build_career_kg_enrichment(
            analysis=analysis,
            cv_markdown=cv_markdown,
            job_title=job_title,
            job_description=job_description,
            experience_level=experience_level,
        )
    except Exception as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "kg_error", "detail": str(exc)})
        return
    analysis_with_kg = analysis.model_copy(update={"kg_enrichment": kg_enrichment})

    try:
        questions = await generate_interview_questions(
            analysis=analysis_with_kg,
            job_title=job_title,
            experience_level=experience_level,
            num_questions=num_questions,
            kg_enrichment=kg_enrichment,
            target_language=target_language,
        )
        validate_questions_language(
            [question.model_dump() for question in questions.questions],
            target_language=target_language,
        )
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

    processing_time_ms = int((time.perf_counter() - started_at) * 1000)

    try:
        db = await get_db()
        cv_repo = CVRepository(db)
        question_repo = QuestionRepository(db)

        cv_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "filename": file_name,
            "job_title": job_title,
            "job_description": job_description,
            "target_language": target_language,
            **analysis_with_kg.model_dump(),
            "model_used": settings.gemini_model,
            "processing_time_ms": processing_time_ms,
        }
        saved_cv = await cv_repo.create(cv_doc)

        enriched_questions = enrich_questions_with_kg_metadata(
            [q.model_dump() for q in questions.questions],
            kg_enrichment,
        )
        question_doc = {
            "session_id": session_id,
            "analysis_id": saved_cv["_id"],
            "job_title": job_title,
            "job_description": job_description,
            "experience_level": experience_level,
            "target_language": target_language,
            "questions": enriched_questions,
            "total_questions": len(enriched_questions),
            "kg_enrichment": kg_enrichment.model_dump(),
        }
        await question_repo.create(question_doc)
    except Exception as exc:
        await _set_status(redis_client, session_id, {"status": "failed", "reason": "db_error", "detail": str(exc)})
        return

    await _set_status(redis_client, session_id, {"status": "done"})


@router.post("/cv/analyze", status_code=status.HTTP_202_ACCEPTED)
async def analyze_cv_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_title: str = Form(...),
    job_description: str = Form(...),
    experience_level: str = Form(...),
    num_questions: int = Form(default=10),
    user_id: str | None = Form(default=None),
):
    settings = get_settings()
    if experience_level not in {"intern", "fresher", "junior", "mid", "senior", "lead"}:
        raise HTTPException(
            status_code=400,
            detail="experience_level must be one of: intern, fresher, junior, mid, senior, lead",
        )
    if num_questions < 1 or num_questions > settings.max_questions:
        raise HTTPException(status_code=400, detail=f"num_questions must be between 1 and {settings.max_questions}")

    file_bytes = await file.read()
    _validate_upload(file, len(file_bytes))

    session_id = str(uuid4())
    await _set_status(request.app.state.redis, session_id, {"status": "processing"})

    background_tasks.add_task(
        _process_pipeline,
        redis_client=request.app.state.redis,
        session_id=session_id,
        file_name=file.filename or "resume",
        file_bytes=file_bytes,
        job_title=job_title,
        job_description=job_description,
        experience_level=experience_level,
        num_questions=num_questions,
        user_id=user_id,
    )

    return {
        "session_id": session_id,
        "status": "processing",
        "estimated_seconds": 20,
    }


@router.get("/cv/{session_id}")
async def get_cv_analysis(request: Request, session_id: str):
    db = await get_db()
    cv_repo = CVRepository(db)
    cv_doc = await cv_repo.get_by_session_id(session_id)
    if cv_doc is not None:
        return cv_doc

    status_payload = await request.app.state.redis.get(f"cv:session:{session_id}")
    if status_payload:
        status_data = json.loads(status_payload)
        if status_data.get("status") == "processing":
            return JSONResponse(status_code=202, content={"status": "processing"})
        if status_data.get("status") == "failed":
            return JSONResponse(status_code=500, content=status_data)

    raise SessionNotFoundException()


@router.get("/cv/history/{user_id}")
async def get_cv_history(user_id: str, page: int = 1, limit: int = 10):
    if page < 1 or limit < 1:
        raise HTTPException(status_code=400, detail="page and limit must be positive")

    db = await get_db()
    cv_repo = CVRepository(db)
    return await cv_repo.list_history_by_user(user_id=user_id, page=page, limit=limit)
