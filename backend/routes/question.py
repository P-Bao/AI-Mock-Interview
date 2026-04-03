import json
import random
from fastapi import APIRouter

router = APIRouter()

@router.get("/question")
def get_question():
    with open("questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    question = random.choice(questions)

    return question