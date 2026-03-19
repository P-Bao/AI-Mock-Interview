import speech_recognition as sr

def speech_to_text():
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("🎤 Nói đi...")
        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(audio, language="vi-VN")
        print("📝 Bạn nói:", text)
        return text
    except:
        return "Không nhận diện được"