from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.routes.evaluation import router as evaluation_router
from core.config import get_settings
from db.mongodb import close_mongodb, init_mongodb


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.ready = False
    app.state.startup_phase = "starting"
    redis_client = None
    try:
        await init_mongodb()
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        app.state.redis = redis_client
        await redis_client.ping()
        app.state.ready = True
        app.state.startup_phase = "ready"
        yield
    except Exception:
        app.state.startup_phase = "failed"
        raise
    finally:
        app.state.ready = False
        app.state.startup_phase = "stopping"
        await close_mongodb()
        if redis_client is not None:
            await redis_client.aclose()


app = FastAPI(title="Evaluation Module API", version="0.1.0", lifespan=lifespan)
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

