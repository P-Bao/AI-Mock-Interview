import os
from dotenv import load_dotenv
import google.generativeai as genai

# đọc file .env
load_dotenv()

# lấy API key
api_key = os.getenv("GEMINI_API_KEY")

# cấu hình genai
genai.configure(api_key=api_key)

# tạo model
model = genai.GenerativeModel('gemini-1.5-flash')

def evaluate_answer(answers):
    full_text = ""

    for item in answers:
        full_text += f"Q: {item['question']}\nA: {item['answer']}\n\n"

    prompt = f"""
    Bạn là giám khảo phỏng vấn.

    Hãy đánh giá toàn bộ phần trả lời sau bằng TIẾNG VIỆT.

    Yêu cầu:
    - Nhận xét tổng thể
    - Chỉ ra điểm mạnh
    - Chỉ ra điểm yếu
    - Gợi ý cải thiện
    - Cho điểm từ 0-10

    Trả về định dạng JSON:
    {{
        "feedback": "nhận xét chi tiết",
        "score": số điểm
    }}

    Nội dung:
    {full_text}
    """

    try:
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Parse JSON từ response
        import json
        result = json.loads(result_text)
        return result
    except Exception as e:
        # Fallback nếu lỗi
        return {
            "feedback": f"Lỗi khi đánh giá: {str(e)}",
            "score": 0
        }