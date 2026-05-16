# Đặc tả API (API reference)

Base URL mặc định (khi chạy local): `http://localhost:8000`

## 1. Health check
Kiểm tra trạng thái hệ thống.
**`GET /health`**
```json
{ "status": "ok" }
```

## 2. Upload và phân tích CV
Gửi file CV và thông tin job description để hệ thống bắt đầu xử lý.
**`POST /api/cv/analyze`**

**Headers:** `Content-Type: multipart/form-data`
**Body parameters:**
- `file` (File - Bắt buộc): File CV định dạng PDF hoặc DOCX.
- `job_title` (String - Bắt buộc): Tên vị trí tuyển dụng (VD: Software Engineer).
- `job_description` (String - Bắt buộc): Mô tả công việc chi tiết.
- `experience_level` (String - Bắt buộc): Chọn 1 trong 6 cấp độ: `intern`, `fresher`, `junior`, `mid`, `senior`, `lead`.
- `num_questions` (Int - Tùy chọn): Số lượng câu hỏi cần sinh (mặc định: 10, tối đa: 20).
- `user_id` (String - Tùy chọn): Mã ID người dùng (dùng để lưu lịch sử).

**Response `202 Accepted`:**
```json
{
  "session_id": "a1b2c3d4-...",
  "status": "processing",
  "estimated_seconds": 20
}
```

## 3. Lấy kết quả phân tích CV
Lấy kết quả đánh giá (điểm mạnh, yếu, độ phù hợp) của một phiên xử lý.
**`GET /api/cv/{session_id}`**

- `200 OK`: Trả về JSON chứa phân tích (bao gồm `kg_enrichment`).
- `202 Accepted`: Task đang xử lý.
- `500 Internal Server Error`: Task bị lỗi (timeout, API error).
- `404 Not Found`: Không tìm thấy session.

**Cấu trúc JSON (trích xuất):**
```json
{
  "overall_match_score": 85,
  "strengths": [...],
  "gaps": [...],
  "kg_enrichment": {
    "enabled": true,
    "source": "Tinix-CareerPathKG",
    "version": "tinix-kg-json-v1:cv-jd",
    "requirement_clusters": [
      {
        "name": "Backend",
        "weight": 0.5,
        "requirements": ["Build REST APIs with Python"],
        "evidence_source": "Tinix-CareerPathKG/data",
        "evidence": ["Build REST APIs with Python -> Python FastAPI"]
      }
    ],
    "skill_matches": [
      {
        "requirement": "Build REST APIs with Python",
        "cv_skill": "Python FastAPI",
        "score": 0.94,
        "relation": "exact",
        "evidence_source": "Tinix-CareerPathKG/data",
        "evidence": ["Tinix positive pair: Build REST APIs with Python -> Python FastAPI"]
      }
    ],
    "skill_gaps": [],
    "question_targets": [],
    "confidence": 1.0
  }
}
```

## 4. Lấy danh sách câu hỏi phỏng vấn
**`GET /api/questions/{session_id}`**

- Trả về mã lỗi tương tự API 3.
- `200 OK`: Trả về mảng câu hỏi có kèm siêu dữ liệu Knowledge Graph.

**Cấu trúc JSON (trích xuất):**
```json
{
  "questions": [
    {
      "question": "Bạn sẽ thiết kế một hệ thống microservices xử lý thanh toán như thế nào để đảm bảo tính nhất quán dữ liệu?",
      "type": "technical",
      "difficulty": "hard",
      "target_skill": "System Design",
      "kg_requirement": "Kiến trúc microservices",
      "kg_match_score": 0.4,
      "kg_gap_severity": "critical",
      "kg_priority": 0.91
    }
  ]
}
```

## 5. Sinh câu hỏi chỉ từ mô tả công việc
**`POST /api/questions/from-job`**

API độc lập khi chưa có CV. Hệ thống tạo một `question_session_id`, xây KG context từ `job_title`, `job_description`, `experience_level`, sinh câu hỏi, lưu vào collection `interview_questions`, và có thể dùng session này cho evaluation.

**Request body:**
```json
{
  "job_title": "Backend Engineer",
  "job_description": "Build REST APIs with Python\nDeploy services with Docker",
  "experience_level": "junior",
  "num_questions": 8,
  "user_id": "user-123"
}
```

**Response `202 Accepted`:**
```json
{
  "session_id": "question-session-id",
  "question_session_id": "question-session-id",
  "status": "processing",
  "source": "job_only"
}
```

Sau đó lấy kết quả bằng **`GET /api/questions/{question_session_id}`**. Document trả về có `source: "job_only"`, `kg_enrichment`, `question_targets`, và metadata KG trên từng câu hỏi.

## 6. Cập nhật điểm/câu trả lời cho câu hỏi
(Phục vụ module phỏng vấn tương tác sau này).
**`PATCH /api/questions/{session_id}/{question_index}/answer`**

**Request body:**
```json
{
  "answer_given": "Tôi sẽ dùng mô hình Saga pattern và Outbox...",
  "answer_score": 85
}
```

## 7. Lịch sử phân tích của user
**`GET /api/cv/history/{user_id}?page=1&limit=10`**

## 8. Tạo đánh giá buổi phỏng vấn
**`POST /api/evaluations`**

Tạo background task đánh giá transcript bằng STAR. Nếu truyền `question_session_id`, hệ thống sẽ lấy `kg_enrichment` và metadata câu hỏi từ `/api/questions/{question_session_id}` để bổ sung Knowledge Graph context cho phần nhận xét. `cv_session_id` vẫn được hỗ trợ như alias tương thích cũ khi question session đến từ `/api/cv/analyze`.

**Request body:**
```json
{
  "session_id": "optional-evaluation-session-id",
  "user_id": "user-123",
  "interview_session_id": "voice-session-123",
  "question_session_id": "session-id-from-cv-analyze-or-from-job",
  "interview": [
    { "role": "model", "text": "How have you deployed services with Docker?" },
    { "role": "user", "text": "I containerized a FastAPI service, wrote a Dockerfile, and deployed it through CI/CD..." }
  ]
}
```

**Response `202 Accepted`:**
```json
{
  "session_id": "evaluation-session-id",
  "status": "processing"
}
```

## 9. Lấy kết quả evaluation
**`GET /api/evaluations/{session_id}`**

- `200 OK`: Trả về evaluation document, bao gồm `kg_context_used` và `kg_enrichment` nếu có.
- `202 Accepted`: Task đang xử lý.
- `500 Internal Server Error`: Task bị lỗi.
- `404 Not Found`: Không tìm thấy session.

Các endpoint phụ:
- **`GET /api/evaluations/history/{user_id}?page=1&limit=10`**
- **`GET /api/evaluations/by-interview/{interview_session_id}`**
