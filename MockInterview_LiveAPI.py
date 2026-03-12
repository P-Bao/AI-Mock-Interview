"""
MockInterview_LiveAPI.py — Phỏng vấn thử Real-time với Gemini Live API Native Audio

Sử dụng Gemini Live API để tạo phiên phỏng vấn IT real-time:
- Mic trực tiếp → stream audio lên Gemini
- Gemini phản hồi bằng giọng nói native (không cần TTS bên ngoài)
- Hỗ trợ barge-in (ngắt lời AI)
- Voice Activity Detection tự động

Yêu cầu:
- GEMINI_API_KEY trong file .env
- PyAudio + python-dotenv + google-genai

Chạy: python MockInterview_LiveAPI.py
Dừng: Ctrl+C
"""

import dotenv
dotenv.load_dotenv()

import asyncio
import os
import sys
import traceback
import pyaudio
from google import genai
from google.genai import types

# === Hỗ trợ Python < 3.11 ===
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

# === Cấu hình Âm thanh ===
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000       # Mic input: 16kHz mono PCM 16-bit
RECEIVE_SAMPLE_RATE = 24000    # AI output: 24kHz
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

# === Cấu hình Gemini Live API ===
client = genai.Client()

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

CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": SYSTEM_INSTRUCTION,
}


# === Biến toàn cục ===
audio_stream = None


async def listen_audio(audio_queue_mic):
    """Capture audio từ microphone và đẩy vào queue."""
    global audio_stream
    
    # Dùng mic mặc định của hệ thống (không chỉ định device index)
    mic_info = pya.get_default_input_device_info()
    print(f"[Mic] Sử dụng mic mặc định: {mic_info['name']}")
    
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE,
    )
    
    kwargs = {"exception_on_overflow": False} if __debug__ else {}
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
        await audio_queue_mic.put({"data": data, "mime_type": "audio/pcm"})


async def send_realtime(session, audio_queue_mic):
    """Stream audio chunks từ mic queue lên Gemini Live API."""
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)


async def receive_audio(session, audio_queue_output):
    """Nhận audio response từ AI và đẩy vào speaker queue."""
    try:
        while True:
            turn = session.receive()
            async for response in turn:
                # Xử lý audio data
                if (response.server_content 
                    and response.server_content.model_turn):
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data and isinstance(part.inline_data.data, bytes):
                            audio_queue_output.put_nowait(part.inline_data.data)
                
                # Xử lý text (transcript) nếu có
                if text := getattr(response, 'text', None):
                    print(f"\n[AI] {text}", end="", flush=True)
            
            # Khi AI kết thúc lượt nói, xoá queue cũ (hỗ trợ barge-in)
            while not audio_queue_output.empty():
                audio_queue_output.get_nowait()
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\n[Lỗi nhận audio] {e}", flush=True)
        traceback.print_exc()


async def play_audio(audio_queue_output):
    """Phát audio từ speaker queue ra loa."""
    stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
    )
    try:
        while True:
            bytestream = await audio_queue_output.get()
            await asyncio.to_thread(stream.write, bytestream)
    except asyncio.CancelledError:
        stream.close()


async def run():
    """Vòng lặp chính — kết nối Live API và chạy 4 task song song."""
    global audio_stream
    
    print("=" * 60)
    print("  MOCK INTERVIEW — Gemini Live API (Real-time)")
    print("=" * 60)
    print(f"  Model  : {MODEL}")
    print(f"  Mic In : {SEND_SAMPLE_RATE}Hz / PCM 16-bit / Mono")
    print(f"  AI Out : {RECEIVE_SAMPLE_RATE}Hz")
    print("-" * 60)
    print("  Hướng dẫn:")
    print("  • Nói trực tiếp vào mic — AI sẽ nghe và trả lời real-time")
    print("  • Bạn có thể ngắt lời AI bất kỳ lúc nào (barge-in)")
    print("  • Nhấn Ctrl+C để kết thúc phỏng vấn")
    print("  • Nên dùng tai nghe để tránh echo")
    print("=" * 60)
    
    audio_queue_output = asyncio.Queue()
    audio_queue_mic = asyncio.Queue(maxsize=5)
    
    try:
        print("\n[Hệ thống] Đang kết nối với Gemini Live API...", flush=True)
        
        async with (
            client.aio.live.connect(model=MODEL, config=CONFIG) as session,
            asyncio.TaskGroup() as tg,
        ):
            print("[Hệ thống] Kết nối thành công! Cuộc phỏng vấn bắt đầu.\n", flush=True)
            
            tg.create_task(listen_audio(audio_queue_mic))
            tg.create_task(send_realtime(session, audio_queue_mic))
            tg.create_task(receive_audio(session, audio_queue_output))
            tg.create_task(play_audio(audio_queue_output))
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"\n[Lỗi] {e}", flush=True)
        traceback.print_exc()
    finally:
        # Cleanup
        if audio_stream:
            try:
                audio_stream.close()
            except Exception:
                pass
        pya.terminate()
        print("\n" + "=" * 60)
        print("  Cuộc phỏng vấn đã kết thúc. Cảm ơn bạn!")
        print("=" * 60)


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("LỖI: Chưa cấu hình GEMINI_API_KEY trong file .env")
        print("Tạo file .env với nội dung: GEMINI_API_KEY=your_key_here")
        sys.exit(1)
    
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n[Hệ thống] Người dùng đã dừng chương trình (Ctrl+C).")
