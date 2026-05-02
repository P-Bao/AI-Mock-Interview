# Đặc tả API

Base URL mặc định local: `http://localhost:8000`

## 1. Health Check

### `GET /health`

Response `200`:

```json
{
  "status": "ok"
}
```

## 2. Upload và phân tích CV

### `POST /api/cv/analyze`

Content-Type: `multipart/form-data`

Form fields:

- `file` (bắt buộc): PDF hoặc DOCX
- `job_title` (bắt buộc): tên vị trí
- `job_description` (bắt buộc): JD
- `experience_level` (bắt buộc): `junior|mid|senior`
- `num_questions` (tùy chọn, mặc định `10`): `1..MAX_QUESTIONS`
- `user_id` (tùy chọn)

Response `202`:

```json
{
  "session_id": "uuid-v4",
  "status": "processing",
  "estimated_seconds": 20
}
```

Lỗi thường gặp:

- `400`: file không phải PDF/DOCX
- `400`: file vượt quá `MAX_FILE_SIZE_MB`
- `400`: `experience_level` không hợp lệ
- `400`: `num_questions` vượt giới hạn

## 3. Lấy kết quả phân tích CV

### `GET /api/cv/{session_id}`

- `200`: trả document phân tích CV từ MongoDB (bao gồm `kg_enrichment`)
- `202`: đang xử lý
- `500`: pipeline lỗi
- `404`: không tồn tại session

Ví dụ `200`:
```json
{
  "overall_match_score": 85,
  "summary": "...",
  "kg_enrichment": {
    "enabled": true,
    "source": "Tinix-CareerPathKG",
    "version": "heuristic",
    "requirement_clusters": [],
    "skill_matches": [],
    "skill_gaps": [],
    "career_guidance": null
  }
}
```

## 4. Lấy danh sách câu hỏi

### `GET /api/questions/{session_id}`

- `200`: trả document câu hỏi (bao gồm metadata từ KG cho từng câu hỏi)
- `202`: đang xử lý
- `500`: pipeline lỗi
- `404`: không tồn tại session

Ví dụ `200` (một phần `questions`):
```json
{
  "questions": [
    {
      "question": "...",
      "kg_metadata": {
        "requirement": "...",
        "match_score": 0.9,
        "gap_severity": "minor"
      }
    }
  ]
}
```

## 5. Cập nhật câu trả lời cho một câu hỏi

### `PATCH /api/questions/{session_id}/{question_index}/answer`

Request body:

```json
{
  "answer_given": "Candidate answer...",
  "answer_score": 75
}
```

Response `200`: trả document `interview_questions` sau cập nhật.

Lỗi thường gặp:

- `400`: `question_index < 0`
- `404`: session không tồn tại
- `404`: question index out of range

## 6. Lịch sử phân tích theo user

### `GET /api/cv/history/{user_id}?page=1&limit=10`

Response `200`:

```json
{
  "items": [],
  "page": 1,
  "limit": 10,
  "total": 0
}
```

Lỗi:

- `400`: `page` hoặc `limit` không hợp lệ.
