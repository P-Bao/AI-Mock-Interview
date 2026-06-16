from contextlib import asynccontextmanager

import asyncio
import logging
import time

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.routes.cv import router as cv_router
from api.routes.evaluation import router as evaluation_router
from api.routes.questions import router as questions_router
from core.config import get_settings
from db.mongodb import close_mongodb, init_mongodb
from services.parser import ResumeParseError



logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ready = False
    app.state.startup_phase = "starting"
    redis_client = None
    logger.info("Startup: initializing application")
    try:
        logger.info("Startup: connecting to MongoDB")
        await init_mongodb()
        logger.info("Startup: MongoDB ready")

        logger.info("Startup: connecting to Redis")
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        app.state.redis = redis_client
        await redis_client.ping()
        logger.info("Startup: Redis ready")

        # MinerU warmup disabled for test runs – no local MinerU binary required.
        logger.info("Startup: MinerU warmup skipped (disabled)")

        app.state.ready = True
        app.state.startup_phase = "ready"
        logger.info("Startup: application ready")
        yield
    except Exception:
        app.state.startup_phase = "failed"
        logger.exception("Startup: application failed")
        raise
    finally:
        logger.info("Shutdown: starting")
        app.state.ready = False
        app.state.startup_phase = "stopping"
        await close_mongodb()
        logger.info("Shutdown: MongoDB closed")
        if redis_client is not None:
            await redis_client.aclose()
            logger.info("Shutdown: Redis closed")
        logger.info("Shutdown: complete")


app = FastAPI(title="CV Module API", version="0.1.0", lifespan=lifespan)
app.include_router(cv_router, prefix="/api")
app.include_router(questions_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")


@app.get("/health")
async def healthcheck() -> dict[str, object]:
    ready = bool(getattr(app.state, "ready", False))
    return {"status": "ok", "ready": ready}


@app.get("/ready")
async def readinesscheck() -> JSONResponse:
    ready = bool(getattr(app.state, "ready", False))
    payload = {
        "status": "ready" if ready else "starting",
        "ready": ready,
        "startup_phase": getattr(app.state, "startup_phase", "unknown"),
    }
    return JSONResponse(content=payload, status_code=200 if ready else 503)
