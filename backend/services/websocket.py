from fastapi import APIRouter, WebSocket
import json
import asyncio

from utils.logger import logger
import time

from services.ai_service import evaluate_answer
from services.stt_service import speech_to_text
from services.tts_service import text_to_speech

router = APIRouter()

@router.websocket("/ws/interview")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    question = "Tell me about yourself"

    logger.info("===== NEW WS SESSION =====")

    await websocket.send_text(json.dumps({
        "type": "question",
        "data": question
    }))

    while True:
        try:
            start = time.time()

            # 🎤 STT
            answer = await asyncio.to_thread(speech_to_text)
            logger.info(f"Answer: {answer}")

            # 🤖 AI
            result = await asyncio.to_thread(
                evaluate_answer, question, answer
            )

            feedback = result["feedback"]
            logger.info(f"Feedback: {feedback}")

            # gửi client
            await websocket.send_text(json.dumps({
                "type": "feedback",
                "data": feedback
            }))

            # 🔊 TTS
            await asyncio.to_thread(text_to_speech, feedback)

            end = time.time()
            logger.info(f"Latency: {end - start:.2f}s")

        except Exception as e:
            logger.error(f"WebSocket error: {e}")

            await websocket.send_text(json.dumps({
                "type": "error",
                "data": str(e)
            }))