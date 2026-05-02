from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI

from api.routes.cv import router as cv_router
from api.routes.questions import router as questions_router
from core.config import get_settings
from db.mongodb import close_mongodb, init_mongodb


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_mongodb()
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield
    finally:
        await close_mongodb()
        await app.state.redis.aclose()


app = FastAPI(title="CV Module API", version="0.1.0", lifespan=lifespan)
app.include_router(cv_router, prefix="/api")
app.include_router(questions_router, prefix="/api")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
