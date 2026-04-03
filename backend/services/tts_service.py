import pyttsx3

engine = pyttsx3.init()

# chọn voice tiếng Việt (nếu có)
voices = engine.getProperty('voices')

for voice in voices:
    print(voice.id)  # in ra để xem

# thử chọn voice có chữ "vi" hoặc "Vietnam"
for voice in voices:
    if "vi" in voice.id.lower() or "vietnam" in voice.name.lower():
        engine.setProperty('voice', voice.id)
        break

def text_to_speech(text):
    engine.say(text)
    engine.runAndWait()