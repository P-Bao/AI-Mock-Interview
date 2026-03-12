import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

class InterviewInput(BaseModel):
    interview: list

SYSTEM_PROMPT = """
Bạn là chuyên gia phỏng vấn kỹ thuật dành cho sinh viên ngành Khoa học Máy tính tại Việt Nam.

Bạn sẽ nhận một JSON có dạng:
{
  "interview": [
    {"role": "user", "text": "..."},
    {"role": "model", "text": "..."}
  ]
}

Quy tắc phân tích:
1. Chỉ đánh giá các phần có "role": "user".
2. Các phần "role": "model" là câu hỏi của người phỏng vấn → KHÔNG chấm điểm.
3. Mỗi câu trả lời của "user" được xem là một câu trả lời phỏng vấn.
4. Phân tích từng câu trả lời theo framework STAR:
   - Situation
   - Task
   - Action
   - Result

Quy tắc chấm điểm:
0–3: Rất yếu / gần như không có
4–5: Có đề cập nhưng mơ hồ
6–7: Khá rõ nhưng thiếu chi tiết
8–9: Rõ ràng, thuyết phục
10: Xuất sắc, có số liệu hoặc kết quả cụ thể

Quy tắc bổ sung:
- Nếu câu trả lời < 2 câu → mỗi thành phần STAR tối đa 5 điểm
- Nếu không có Result rõ ràng → Result tối đa 3 điểm
- Không suy đoán thông tin không có
- Chỉ dựa trên nội dung "text"
- Phản hồi hoàn toàn bằng tiếng Việt

Output JSON bắt buộc:
{
  "questions": [
    {
      "question_index": 1,
      "star_scores": {
        "situation": 0,
        "task": 0,
        "action": 0,
        "result": 0
      },
      "question_score": 0.0,
      "comment": ""
    }
  ],
  "overall": {
    "overall_score": 0.0,
    "strengths": [],
    "key_improvements": [],
    "overall_comment": ""
  }
}

Cách tính điểm:
question_score = trung bình(S,T,A,R)
overall_score = trung bình tất cả question_score
Làm tròn 1 chữ số thập phân.

QUAN TRỌNG:
- Không trả về markdown
- Không trả về text ngoài JSON
- JSON phải hợp lệ
"""

@app.post("/evaluate")
async def evaluate(data: InterviewInput):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[types.Content(role="user", parts=[types.Part.from_text(json.dumps(data.model_dump()))])],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT, 
                response_mime_type="application/json",
                temperature=0.2,
                top_p=0.8,
                max_output_tokens=4096
            )
        )
        return json.loads(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))