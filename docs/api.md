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
    "version": "heuristic",
    "requirement_clusters": [],
    "skill_matches": [],
    "skill_gaps": []
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
      "kg_metadata": {
        "requirement": "Kiến trúc microservices",
        "match_score": 0.4,
        "gap_severity": "critical"
      }
    }
  ]
}
```

## 5. Cập nhật điểm/câu trả lời cho câu hỏi
(Phục vụ module phỏng vấn tương tác sau này).
**`PATCH /api/questions/{session_id}/{question_index}/answer`**

**Request body:**
```json
{
  "answer_given": "Tôi sẽ dùng mô hình Saga pattern và Outbox...",
  "answer_score": 85
}
```

## 6. Lịch sử phân tích của user
**`GET /api/cv/history/{user_id}?page=1&limit=10`**
