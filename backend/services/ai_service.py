import os
from dotenv import load_dotenv
from google import genai

# đọc file .env
load_dotenv()

# lấy API key
api_key = os.getenv("GEMINI_API_KEY")

# tạo client
client = genai.Client(api_key=api_key)

def evaluate_answer(question, answer):

    prompt = f"""
    You are an HR interviewer.

    Evaluate this interview answer.

    Question: {question}
    Answer: {answer}

    Give:
    - score from 1 to 10
    - short feedback
    """

    response = client.models.generate_content(
        model="models/gemini-2.5-flash-lite",
        contents=prompt
    )

    return {
        "feedback": response.text
    }