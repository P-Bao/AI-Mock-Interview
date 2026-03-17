from fastapi import FastAPI
from routes.evaluate import router as evaluate_router
from routes.question import router as question_router

app = FastAPI()

app.include_router(evaluate_router)
app.include_router(question_router)