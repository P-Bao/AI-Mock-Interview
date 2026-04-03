from fastapi import APIRouter
import time

from services.stt_service import speech_to_text
from services.ai_service import evaluate_answer
from services.tts_service import text_to_speech
from utils.logger import logger

router = APIRouter()

@router.get("/voice-interview")
def voice_interview():

    start = time.time()

    logger.info("===== NEW SESSION =====")

    # 1. question
    question = "Tell me about yourself"
    logger.info(f"Question: {question}")

    # 2. STT
    answer = speech_to_text()
    logger.info(f"Answer: {answer}")

    # 3. AI
    result = evaluate_answer(question, answer)
    feedback = result["feedback"]
    logger.info(f"Feedback: {feedback}")

    # 4. TTS
    text_to_speech(feedback)

    end = time.time()
    latency = end - start
    logger.info(f"Latency: {latency:.2f}s")

    return {
        "question": question,
        "answer": answer,
        "feedback": feedback,
        "latency": latency
    }