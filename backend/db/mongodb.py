from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from core.config import get_settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_mongodb() -> None:
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_atlas_uri)
    _db = _client[settings.mongodb_db_name]
    await _create_indexes(_db)


async def close_mongodb() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


async def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB is not initialized")
    return _db


async def _create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.cv_analyses.create_index([("session_id", ASCENDING)], unique=True)
    await db.cv_analyses.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.cv_analyses.create_index([("created_at", DESCENDING)])

    await db.interview_questions.create_index([("session_id", ASCENDING)], unique=True)
    await db.interview_questions.create_index([("analysis_id", ASCENDING)])
    await db.interview_questions.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.interview_questions.create_index([("source", ASCENDING)])
    await db.interview_questions.create_index([("target_language", ASCENDING)])

    await db.evaluations.create_index([("session_id", ASCENDING)], unique=True)
    await db.evaluations.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db.evaluations.create_index([("interview_session_id", ASCENDING)])
    await db.evaluations.create_index([("question_session_id", ASCENDING)])
    await db.evaluations.create_index([("cv_session_id", ASCENDING)])
    await db.evaluations.create_index([("created_at", DESCENDING)])


def normalize_mongo_doc(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    document["_id"] = str(document["_id"])
    return document
