"""
MockInterview_ValtecTTS.py
Mock Interview sử dụng ValtecTTS qua API (local Gradio server).
Stream mode: chia text thành từng câu, phát câu đầu trong khi synthesize câu tiếp.
"""

import dotenv
dotenv.load_dotenv()

import os
import sys
import re
import wave
import shutil
import time
import pyaudio
import threading
from concurrent.futures import ThreadPoolExecutor, Future
import pygame
from google import genai

# Monkey-patch gradio_client bug
try:
    import gradio_client.utils as _gc_utils
    _orig = _gc_utils._json_schema_to_python_type
    def _patched(schema, defs=None):
        if isinstance(schema, bool):
            return "Any"
        return _orig(schema, defs)
    _gc_utils._json_schema_to_python_type = _patched
except Exception:
    pass

from gradio_client import Client as GradioClient

# === Cấu hình ValtecTTS API ===
VALTEC_API_URL = "http://localhost:7860"  # Local Gradio server
VOICE_NAME = "Thu Hà"  # Thu Hà, Minh Đức, Thanh Tâm, Quang Huy, Ngọc Ánh, Hoàng Nam

# === Cấu hình Âm thanh Ghi âm ===
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

pya = pyaudio.PyAudio()
pygame.mixer.init()

# === Cấu hình Gemini ===
client = genai.Client()
MODEL_ID = "gemini-2.5-flash"

system_instruction = """
Bạn là một người phỏng vấn IT chuyên nghiệp, thân thiện và hữu ích.
Bạn luôn giao tiếp hoàn toàn bằng tiếng Việt.
Nhiệm vụ của bạn là phỏng vấn ứng viên, đặt câu hỏi từng bước.
Khi ứng viên trả lời bằng giọng nói (được chuyển thành text), hãy nhận xét ngắn gọn, chỉ ra điểm tốt/điểm cần cải thiện, sau đó đặt câu hỏi tiếp theo có liên quan.
Giọng điệu của bạn tự nhiên, rõ ràng.
Luôn kết thúc bằng một câu hỏi tiếp nối. Chỉ nói những thứ cần để đọc lên bằng text-to-speech.
Tuyệt đối KHÔNG DÙNG emoji, dấu ngoặc kép, hay các ký tự đặc biệt khó đọc.
Khi gặp từ viết tắt tiếng Anh, hãy đọc rõ từng chữ cái theo phiên âm tiếng Việt. Ví dụ: AI thành Ây-Ai, NLP thành En-Eo-Pi, API thành Ây-Pi-Ai, SQL thành Ét-Kiu-Eo, HTML thành Ếch-Ti-Em-Eo, CSS thành Xi-Ét-Ét, IT thành Ai-Ti, ML thành Em-Eo, DevOps thành Đép-Óp.
"""

CONFIG = {
    "system_instruction": system_instruction,
    "temperature": 0.7,
}

# === Biến Toàn cục ===
recording = False
frames = []


# ============================================================
#  Text splitting
# ============================================================

def split_sentences(text):
    """Chia text thành các câu dựa trên dấu chấm câu tiếng Việt.
    Gộp các đoạn quá ngắn vào câu trước đó."""
    # Tách theo dấu . ! ? và giữ lại dấu
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    parts = [p.strip() for p in parts if p.strip()]

    # Gộp đoạn ngắn (<15 ký tự) vào câu trước
    merged = []
    for part in parts:
        if merged and len(part) < 15:
            merged[-1] = merged[-1] + " " + part
        else:
            merged.append(part)

    return merged if merged else [text]


# ============================================================
#  TTS API call
# ============================================================

def synthesize_sentence(valtec_client, text, voice_name):
    """Gọi API synthesize 1 câu, trả về audio file path."""
    result = valtec_client.predict(
        text=text,
        voice_choice=voice_name,
        custom_audio=None,
        speed=1,
        noise_scale=0.667,
        noise_scale_w=0.8,
        api_name="/synthesize_fn"
    )
    audio_info = result[0]
    if isinstance(audio_info, dict):
        return audio_info.get('path', '')
    return str(audio_info)


def play_audio_file(audio_path):
    """Phát 1 file audio bằng pygame, blocking cho đến khi xong."""
    if not os.path.exists(audio_path):
        return
    pygame.mixer.music.load(audio_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.mixer.music.unload()


def play_tts_streamed(valtec_client, text, voice_name):
    """Stream TTS: synthesize câu tiếp theo song song với phát câu hiện tại.
    
    Flow:
      1. Chia text thành các câu
      2. Submit synthesize câu 1 → chờ kết quả → bắt đầu phát
      3. Trong khi phát câu 1, submit synthesize câu 2 (prefetch)
      4. Khi phát xong câu 1, kết quả câu 2 đã sẵn sàng → phát ngay
      5. Lặp lại...
    """
    if not text:
        return

    sentences = split_sentences(text)
    n = len(sentences)
    print(f"\n🔊 [ValtecTTS] AI đang phát biểu... ({n} câu)")

    executor = ThreadPoolExecutor(max_workers=1)
    t_start = time.time()

    try:
        # Submit câu đầu tiên
        future = executor.submit(synthesize_sentence, valtec_client, sentences[0], voice_name)
        audio_path = future.result()  # Chờ câu 1 xong

        t_first = time.time() - t_start
        print(f"   Câu 1/{n} ready in {t_first:.1f}s — playing...")

        for i in range(n):
            # Prefetch câu tiếp theo (nếu còn) TRƯỚC khi phát câu hiện tại
            next_future = None
            if i + 1 < n:
                next_future = executor.submit(
                    synthesize_sentence, valtec_client, sentences[i + 1], voice_name
                )

            # Phát audio câu hiện tại
            play_audio_file(audio_path)

            # Lấy kết quả câu tiếp theo (đã synthesize song song)
            if next_future:
                audio_path = next_future.result()
                print(f"   Câu {i+2}/{n} ready — playing...")

        t_total = time.time() - t_start
        print(f"   ✓ Done ({t_total:.1f}s total, first response: {t_first:.1f}s)")

    except Exception as e:
        print(f"[Lỗi ValtecTTS] {e}")
    finally:
        executor.shutdown(wait=False)


# ============================================================
#  Audio Recording
# ============================================================

def record_audio(filename="user_audio.wav"):
    """Ghi âm từ Micro"""
    global recording, frames
    frames = []

    print("\n" + "=" * 50)
    print("🎤  Sẵn sàng ghi âm!")
    input("👉  Nhấn [ENTER] để BẮT ĐẦU nói...")

    recording = True
    print("\n[ĐANG GHI ÂM...] Nhấn [ENTER] lần nữa để dừng")

    stream = pya.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                      input=True, frames_per_buffer=CHUNK)

    def capture():
        while recording:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                pass

    t = threading.Thread(target=capture)
    t.start()
    input()
    recording = False
    t.join()

    print("[ĐÃ LƯU] Đang gửi câu trả lời lên Gemini...")

    stream.stop_stream()
    stream.close()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(pya.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    return filename


# ============================================================
#  Main
# ============================================================

def main():
    print("=" * 60)
    print("  Mock Interview — ValtecTTS (Local API + Stream)")
    print("=" * 60)

    # 1. Connect to local ValtecTTS Gradio server
    print(f"[Hệ thống] Connecting to ValtecTTS ({VALTEC_API_URL})...")
    valtec_client = GradioClient(VALTEC_API_URL)
    print(f"[Hệ thống] ✓ Connected! Giọng AI: {VOICE_NAME}")

    # 2. Khởi tạo Gemini chat
    chat = client.chats.create(model=MODEL_ID, config=CONFIG)
    print("\n[Hệ thống] Đang yêu cầu AI bắt đầu cuộc phỏng vấn...")

    try:
        response = chat.send_message("Hãy bắt đầu cuộc phỏng vấn bằng tiếng Việt ngay bây giờ.")
        if response.text:
            print("\n🤖 AI:", response.text)
            play_tts_streamed(valtec_client, response.text, VOICE_NAME)
    except Exception as e:
        print("Lỗi khi kết nối:", e)
        return

    temp_wav = "temp_user_response.wav"

    # 3. Vòng lặp phỏng vấn
    while True:
        try:
            record_audio(temp_wav)

            print("\n[Hệ thống] AI đang lắng nghe và suy nghĩ...")
            audio_file = client.files.upload(file=temp_wav)
            response = chat.send_message(audio_file)

            if response.text:
                print("\n🤖 AI:", response.text)
                play_tts_streamed(valtec_client, response.text, VOICE_NAME)

        except KeyboardInterrupt:
            print("\n\n[Hệ thống] Đã dừng chương trình (Ctrl+C).")
            break
        except Exception as e:
            print(f"\n[Lỗi] {e}")

    # Cleanup
    if os.path.exists(temp_wav):
        os.remove(temp_wav)
    pya.terminate()
    pygame.quit()
    print("Đã kết thúc Mock Interview.")


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("LỖI: Chưa cấu hình GEMINI_API_KEY trong file .env")
        sys.exit(1)
    main()
