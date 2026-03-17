#nơi viết api
from fastapi import APIRouter
from services.ai_service import evaluate_answer


router = APIRouter()

@router.post("/evaluate")
async def evaluate(data: dict):

    question = data["question"]
    answer = data["answer"]

    result = evaluate_answer(question, answer)

    return result


