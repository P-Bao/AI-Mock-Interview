from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongodb import normalize_mongo_doc


class QuestionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.interview_questions

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document.setdefault("created_at", datetime.now(timezone.utc))
        result = await self.collection.insert_one(document)
        saved = await self.collection.find_one({"_id": result.inserted_id})
        return normalize_mongo_doc(saved) or {}

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"session_id": session_id})
        return normalize_mongo_doc(doc)

    async def update_answer(
        self,
        session_id: str,
        question_index: int,
        answer_given: str,
        answer_score: int | None,
    ) -> dict[str, Any] | None:
        update_fields = {
            f"questions.{question_index}.answered": True,
            f"questions.{question_index}.answer_given": answer_given,
            f"questions.{question_index}.answer_score": answer_score,
        }
        await self.collection.update_one({"session_id": session_id}, {"$set": update_fields})
        updated = await self.collection.find_one({"session_id": session_id})
        return normalize_mongo_doc(updated)
