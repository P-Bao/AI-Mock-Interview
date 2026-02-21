import dotenv
dotenv.load_dotenv()

import os
import sys
import wave
import pyaudio
import threading
import asyncio
import edge_tts
import pygame
from google import genai

# === Cấu hình Âm thanh Ghi âm ===
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

pya = pyaudio.PyAudio()
pygame.mixer.init()

# === Cấu hình Text-To-Speech (Microsoft Edge Neural) ===
# Giọng nữ tiếng Việt chất lượng cao siêu tự nhiên
VOICE_NAME = "vi-VN-HoaiMyNeural" 
print(f"[Hệ thống] Đã cấu hình Giọng đọc AI Trợ lý: {VOICE_NAME}")

# === Cấu hình Gemini ===
client = genai.Client() 
# Dùng bản text tốc độ cao siêu ổn định
MODEL_ID = "gemini-2.5-flash" 

system_instruction = """
Bạn là một người phỏng vấn IT chuyên nghiệp, thân thiện và hữu ích.
Bạn luôn giao tiếp hoàn toàn bằng tiếng Việt.
Nhiệm vụ của bạn là phỏng vấn ứng viên, đặt câu hỏi từng bước.
Khi ứng viên trả lời bằng giọng nói (được chuyển thành text), hãy nhận xét ngắn gọn, chỉ ra điểm tốt/điểm cần cải thiện, sau đó đặt câu hỏi tiếp theo có liên quan.
Giọng điệu của bạn tự nhiên, rõ ràng.
Luôn kết thúc bằng một câu hỏi tiếp nối. Chỉ nói những thứ cần để đọc lên bằng text-to-speech.
Tuyệt đối KHÔNG DÙNG emoji, dấu ngoặc kép, hay các ký tự đặc biệt khó đọc.
"""

CONFIG = {
    "system_instruction": system_instruction,
    "temperature": 0.7,
}

# === Khai báo Biến Toàn cục cho Ghi âm ===
recording = False
frames = []

def record_audio(filename="user_audio.wav"):
    """Ghi âm từ Micro sử dụng input() và luồng (Thread)"""
    global recording, frames
    frames = []
    
    print("\n" + "="*50)
    print("🎤  Sẵn sàng ghi âm!")
    input("👉  Nhấn phím [ENTER] để BẮT ĐẦU nói...")
    
    recording = True
    print("\n[ĐANG GHI ÂM...] (Hãy nói đi, nhấn [ENTER] lần nữa để dừng)")
    
    stream = pya.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    def capture_audio():
        while recording:
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception:
                pass

    t = threading.Thread(target=capture_audio)
    t.start()
    
    # Đợi người dùng nhấn Enter lần 2 để dừng
    input()
    recording = False
    t.join()
    
    print("[ĐÃ LƯU] Đang gửi câu trả lời lên Gemini...")
            
    stream.stop_stream()
    stream.close()

    # Lưu ra file WAV tạm thời
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(pya.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    return filename

async def play_text_to_speech(text, filename="ai_audio.mp3"):
    """Sử dụng edge-tts tổng hợp giọng nói đa ngôn ngữ siêu mượt và phát mp3"""
    if not text: return
    try:
        print("\n🔊 [Hệ thống] AI đang phát biểu...")
        communicate = edge_tts.Communicate(text, VOICE_NAME)
        await communicate.save(filename)
        
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        pygame.mixer.music.unload()
    except Exception as e:
        print(f"[Lỗi Edge TTS] {e}")

# === Vòng lặp chính (Chat Session) ===
def main():
    print("Khởi động phiên Mock Interview (Text + Edge Neural TTS)...")
    
    chat = client.chats.create(
        model=MODEL_ID,
        config=CONFIG
    )
    
    print("\n[Hệ thống] Đang yêu cầu AI bắt đầu cuộc phỏng vấn...")
    try:
        response = chat.send_message("Hãy bắt đầu cuộc phỏng vấn bằng tiếng Việt ngay bây giờ.")
        
        if response.text:
            print("\n🤖 AI:", response.text)
            asyncio.run(play_text_to_speech(response.text))
            
    except Exception as e:
        print("Lỗi khi kết nối ban đầu:", e)
        return

    temp_wav = "temp_user_response.wav"
    ai_mp3 = "ai_audio.mp3"
    
    while True:
        try:
            # 1. Ghi âm người dùng
            record_audio(temp_wav)
            
            # 2. Upload file âm thanh lên Gemini
            print("\n[Hệ thống] AI đang lắng nghe và suy nghĩ...")
            audio_file = client.files.upload(file=temp_wav)
            
            # 3. Gửi file vào Chat Session
            response = chat.send_message(audio_file)
            
            # 4. Hiển thị Text và Phát Audio bằng TTS
            if response.text:
                print("\n🤖 AI:", response.text)
                asyncio.run(play_text_to_speech(response.text, ai_mp3))
                
        except KeyboardInterrupt:
            print("\n\n[Hệ thống] Người dùng đã dừng chương trình (Ctrl+C).")
            break
        except Exception as e:
            print(f"\n[Lỗi] Đã xảy ra sự cố: {e}")
            
    # Cleanup dọn dẹp biến, file tạm
    if os.path.exists(temp_wav): os.remove(temp_wav)
    if os.path.exists(ai_mp3): os.remove(ai_mp3)
    pya.terminate()
    pygame.quit()
    print("Đã kết thúc Mock Interview.")

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("LỖI: Chưa cấu hình GEMINI_API_KEY trong file .env")
        sys.exit(1)
    
    main()
