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
    Bạn là người phỏng vấn nhân sự.

    Hãy đánh giá câu trả lời phỏng vấn này.

    Câu hỏi: {question}

    Câu trả lời: {answer}

Cho điểm:

- điểm từ 1 đến 10

- phản hồi ngắn gọn
    """

    response = client.models.generate_content(
        model="models/gemini-2.5-flash-lite",
        contents=prompt
    )

    return {
        "feedback": response.text
    }

def evaluate_full_interview(history):
    # history: list of {"question": "...", "answer": "..."}
    
    formatted_history = ""
    for i, item in enumerate(history):
        formatted_history += f"Lượt {i+1}:\nCâu hỏi: {item['question']}\nCâu trả lời: {item['answer']}\n\n"

    prompt = f"""
    Bạn là một chuyên gia phỏng vấn nhân sự dày dạn kinh nghiệm. 
    Hãy xem lại toàn bộ nội dung buổi phỏng vấn dưới đây và đưa ra đánh giá toàn diện.

    {formatted_history}

    Vui lòng cung cấp:
    1. Điểm tổng kết (từ 1 đến 10)
    2. Các điểm mạnh chính của ứng viên
    3. Các điểm cần cải thiện
    4. Kết luận cuối cùng/Lời khuyên dành cho ứng viên
    """

    response = client.models.generate_content(
        model="models/gemini-2.5-flash-lite",
        contents=prompt
    )

    return {
        "final_report": response.text
    }