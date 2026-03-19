from fastapi import FastAPI
from routes.evaluate import router as evaluate_router
from routes.question import router as question_router
from routes.voice import router as voice_router
app = FastAPI()

app.include_router(evaluate_router)
app.include_router(question_router)
app.include_router(voice_router)