from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from db.mongodb import normalize_mongo_doc


class EvaluationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db.evaluations

    async def create(self, document: dict[str, Any]) -> dict[str, Any]:
        document.setdefault("created_at", datetime.now(timezone.utc))
        result = await self.collection.insert_one(document)
        saved = await self.collection.find_one({"_id": result.inserted_id})
        return normalize_mongo_doc(saved) or {}

    async def get_by_session_id(self, session_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"session_id": session_id})
        return normalize_mongo_doc(doc)

    async def get_by_interview_session_id(self, interview_session_id: str) -> dict[str, Any] | None:
        doc = await self.collection.find_one({"interview_session_id": interview_session_id})
        return normalize_mongo_doc(doc)

    async def list_history_by_user(self, user_id: str, page: int, limit: int) -> dict[str, Any]:
        skip = max(page - 1, 0) * limit
        cursor = self.collection.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)

        items = [normalize_mongo_doc(doc) async for doc in cursor]
        total = await self.collection.count_documents({"user_id": user_id})

        return {
            "items": items,
            "page": page,
            "limit": limit,
            "total": total,
        }
