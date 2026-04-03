from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
import asyncio
import json

from services.ai_service import evaluate_answer

router = APIRouter()

@router.websocket("/ws/interview")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    question = "Tell me about yourself"

    print("===== NEW WS SESSION =====")

    # gửi câu hỏi
    await websocket.send_text(json.dumps({
        "type": "question",
        "data": question
    }))

    while True:
        try:
            # 🔥 nhận từ frontend
            data = await websocket.receive_text()
            data = json.loads(data)

            answer = data.get("answer", "")

            print("USER:", answer)

            # 🤖 AI
            result = await asyncio.to_thread(
                evaluate_answer, question, answer
            )

            feedback = result["feedback"]

            print("AI:", feedback)

            # 📤 gửi lại frontend
            await websocket.send_text(json.dumps({
                "type": "feedback",
                "data": feedback
            }))

        except WebSocketDisconnect:
            print("❌ Client disconnected")
            break

        except Exception as e:
            print("🔥 ERROR:", e)

            await websocket.send_text(json.dumps({
                "type": "error",
                "data": str(e)
            }))