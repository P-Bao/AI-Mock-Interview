from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
import asyncio
import json
import os

from services.ai_service import evaluate_answer
from services.tts_service import text_to_speech

router = APIRouter()


#  load câu hỏi từ file JSON
def load_questions():
    file_path = os.path.join(os.path.dirname(__file__), "../questions.json")
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.websocket("/ws/interview")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    questions_data = load_questions()
    questions = [q["question"] for q in questions_data]

    current = 0
    answers = []

    print("===== NEW WS SESSION =====")

    # gửi câu hỏi đầu tiên
    await websocket.send_text(json.dumps({
        "type": "question",
        "data": questions[current]
    }))

    while True:
        try:
            # nhận dữ liệu từ frontend
            data = await websocket.receive_text()
            data = json.loads(data)

            answer = data.get("answer", "")
            question = questions[current]

            print("Q:", question)
            print("USER:", answer)

            # lưu lại câu trả lời
            answers.append({
                "question": question,
                "answer": answer
            })

            current += 1

            # còn câu hỏi → hỏi tiếp
            if current < len(questions):
                await websocket.send_text(json.dumps({
                    "type": "question",
                    "data": questions[current]
                }))

            else:
                #  hết câu → đánh giá tổng
                print(" Evaluating full interview...")

                # báo frontend đang xử lý
                await websocket.send_text(json.dumps({
                    "type": "loading",
                    "data": "AI đang đánh giá..."
                }))

                result = await asyncio.to_thread(
                    evaluate_answer, answers
                )

                feedback = result.get("feedback", "")
                score = result.get("score", 0)

                print("FINAL AI:", feedback)
                print("SCORE:", score)

                # gửi kết quả cuối
                await websocket.send_text(json.dumps({
                    "type": "final_result",
                    "answers": answers,
                    "feedback": feedback,
                    "score": score
                }))

                #  AI nói tiếng Việt
                await asyncio.to_thread(text_to_speech, feedback)

                break

        except WebSocketDisconnect:
            print(" Client disconnected")
            break

        except Exception as e:
            print(" ERROR:", e)

            await websocket.send_text(json.dumps({
                "type": "error",
                "data": str(e)
            }))