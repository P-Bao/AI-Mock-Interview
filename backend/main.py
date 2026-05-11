from fastapi import FastAPI
from routes.evaluate import router as evaluate_router
from routes.question import router as question_router
from routes.voice import router as voice_router
from routes.websocket import router as ws_router
from routes.auth import router as auth_router
from routes.users import router as users_router

app = FastAPI()

app.include_router(evaluate_router)
app.include_router(question_router)
app.include_router(voice_router)
app.include_router(ws_router)
app.include_router(auth_router)
app.include_router(users_router)