import asyncio
import os
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Quản lý kênh phát Transcript và Kết quả
class TranscriptManager:
    def __init__(self):
        self.active_connections = list()
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, data: dict):
        for connection in self.active_connections:
            try: await connection.send_json(data)
            except Exception: continue

manager = TranscriptManager()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options=dict(api_version="v1beta"))

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

SYSTEM_INSTRUCTION = """
Bạn là một người phỏng vấn IT chuyên nghiệp, thân thiện và hữu ích.
Bạn luôn giao tiếp hoàn toàn bằng tiếng Việt.
Nhiệm vụ của bạn là phỏng vấn ứng viên cho vị trí lập trình viên.

Quy tắc phỏng vấn:
1. Bắt đầu bằng việc chào hỏi và tự giới thiệu là người phỏng vấn.
2. Hỏi ứng viên muốn phỏng vấn vị trí gì (Frontend, Backend, Fullstack, DevOps, v.v.).
3. Đặt câu hỏi từng bước, từ dễ đến khó, phù hợp với vị trí đã chọn.
4. Sau mỗi câu trả lời của ứng viên, nhận xét ngắn gọn (điểm tốt và điểm cần cải thiện).
5. Sau đó đặt câu hỏi tiếp theo có liên quan.
6. Giọng điệu tự nhiên, rõ ràng, khích lệ ứng viên.
7. Không nói quá dài, mỗi lượt chỉ nên từ 2 đến 4 câu.
8. Sau khoảng 8 đến 10 câu hỏi, tổng kết và đánh giá tổng thể.
"""

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=['AUDIO', 'TEXT'],
    system_instruction=SYSTEM_INSTRUCTION,
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck"))
    )
)

@app.websocket("/ws/transcript")
async def transcript_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: manager.disconnect(websocket)

@app.websocket("/ws/audio")
async def audio_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_history = list()
    current_ai_text = ""

    try:
        async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as gemini_session:
            async def send():
                while True:
                    data = await websocket.receive_bytes()
                    await gemini_session.send(input=data, end_of_turn=False)
            async def receive():
                nonlocal current_ai_text
                async for message in gemini_session.receive():
                    if message.server_content and message.server_content.input_transcription:
                        trans = message.server_content.input_transcription
                        if trans.finished: session_history.append(dict(role="user", text=trans.text))
                    if message.server_content and message.server_content.model_turn:
                        for part in message.server_content.model_turn.parts:
                            if part.text: current_ai_text += part.text
                            if part.inline_data: await websocket.send_bytes(part.inline_data.data)
                        if message.server_content.turn_complete:
                            session_history.append(dict(role="model", text=current_ai_text))
                            current_ai_text = ""
            await asyncio.gather(send(), receive())
    except WebSocketDisconnect:
        # PIPELINE: Kết thúc -> Gọi Đánh giá 
        async with httpx.AsyncClient() as http_client:
            try:
                # Gọi Evaluation API trên port 8001
                resp = await http_client.post("http://localhost:8001/evaluate", json=dict(interview=session_history))
                eval_data = resp.json()
                # Phát (Broadcast) Transcript + Đánh giá
                await manager.broadcast({
                    "type": "interview_result",
                    "transcript": session_history,
                    "evaluation": eval_data
                })
            except Exception as e:
                print(f"Pipeline Error: {e}")
    finally:
        try: await websocket.close()
        except Exception: pass