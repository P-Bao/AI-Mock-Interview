from gtts import gTTS
import os
import uuid

def text_to_speech(text):
    filename = f"audio_{uuid.uuid4().hex}.mp3"

    tts = gTTS(text=text, lang='vi')
    tts.save(filename)

    os.system(f"start {filename}")  # Windows

    return filename