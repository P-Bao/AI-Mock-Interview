import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.exceptions import SessionNotFoundException
from db.mongodb import get_db
from db.repositories.question_repo import QuestionRepository
from models.interview import AnswerUpdateRequest

router = APIRouter(tags=["questions"])


@router.get("/questions/{session_id}")
async def get_questions(request: Request, session_id: str):
    db = await get_db()
    repo = QuestionRepository(db)
    doc = await repo.get_by_session_id(session_id)
    if doc is not None:
        return doc

    status_payload = await request.app.state.redis.get(f"cv:session:{session_id}")
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
