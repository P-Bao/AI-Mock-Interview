from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
import asyncio
import json
import random
import os
import uuid
from datetime import datetime
from services.ai_service import evaluate_answer, evaluate_full_interview

router = APIRouter()

@router.websocket("/ws/interview")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    session_id = str(uuid.uuid4())[:8]
    interview_history = []
    asked_questions = set()
    
    # Lấy danh sách câu hỏi
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            questions = json.load(f)
    except Exception as e:
        print(f"Error loading questions: {e}")
        questions = [{"category": "intro", "question": "Tell me about yourself"}]

    # Chọn câu hỏi khởi đầu
    question_obj = random.choice(questions)
    question = question_obj["question"]
    asked_questions.add(question)

    print(f"===== NEW SESSION [{session_id}]: {question} =====")

    # gửi câu hỏi đầu tiên
    await websocket.send_text(json.dumps({
        "type": "question",
        "data": question
    }))

    while True:
        try:
            data = await websocket.receive_text()
            data = json.loads(data)

            msg_type = data.get("type", "answer")

            # Trường hợp 1: Kết thúc phỏng vấn
            if msg_type == "finish":
                print(f"[{session_id}] Kết thúc buổi phỏng vấn...")
                
                if not interview_history:
                    await websocket.send_text(json.dumps({
                        "type": "feedback",
                        "data": "Không có dữ liệu phỏng vấn để đánh giá."
                    }))
                    break

                # 🤖 Đánh giá tổng hợp
                await websocket.send_text(json.dumps({
                    "type": "feedback",
                    "data": "Đang tổng hợp nội dung và lập báo cáo, vui lòng đợi trong giây lát..."
                }))
                
                try:
                    result = await asyncio.to_thread(
                        evaluate_full_interview, interview_history
                    )
                    final_report = result["final_report"]
                    
                    # 💾 Lưu vào file JSON
                    interview_data = {
                        "id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "history": interview_history,
                        "evaluation": final_report
                    }
                    
                    os.makedirs("logs", exist_ok=True)
                    file_path = f"logs/interview_{session_id}.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(interview_data, f, ensure_ascii=False, indent=4)
                    
                    print(f"[{session_id}] Đã lưu lịch sử vào {file_path}")

                    # 📤 Gửi report cuối cùng
                    await websocket.send_text(json.dumps({
                        "type": "feedback",
                        "data": final_report
                    }))
                except Exception as e:
                    print(f"Lỗi khi kết thúc: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "data": "Quá trình đánh giá thất bại. Vui lòng thử lại sau."
                    }))
                
                break

            # Trường hợp 2: Nhận câu trả lời thường xuyên
            answer = data.get("answer", "")
            if answer:
                print(f"[{session_id}] USER: {answer}")
                
                # Lưu vào lịch sử
                interview_history.append({
                    "question": question,
                    "answer": answer
                })

                # 🆕 Chọn câu hỏi tiếp theo mà chưa hỏi
                available_questions = [q for q in questions if q["question"] not in asked_questions]
                
                if not available_questions:
                    print(f"[{session_id}] All questions asked. Resetting list.")
                    asked_questions.clear()
                    # Loại trừ câu hỏi hiện tại để tránh bị lặp ngay lập tức
                    available_questions = [q for q in questions if q["question"] != question]
                
                question_obj = random.choice(available_questions)
                question = question_obj["question"]
                asked_questions.add(question)
                
                print(f"[{session_id}] NEXT: {question}")
                
                await websocket.send_text(json.dumps({
                    "type": "question",
                    "data": question
                }))

        except WebSocketDisconnect:
            print(f"[{session_id}] Client disconnected")
            break
        except Exception as e:
            print(f"🔥 ERROR: {e}")
            break