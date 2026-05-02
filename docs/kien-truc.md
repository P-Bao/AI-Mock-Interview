# Kiến trúc hệ thống

## 1. Mục tiêu

Module backend nhận CV từ frontend, phân tích mức độ phù hợp với JD, sinh bộ câu hỏi phỏng vấn và trả kết quả theo `session_id`.

## 2. Thành phần chính

- `FastAPI`:
  - Nhận upload CV
  - Cung cấp API poll kết quả
- `MinerU CLI`:
  - Parse PDF/DOCX sang markdown text
- `Gemini API`:
  - Phân tích CV
  - Sinh câu hỏi phỏng vấn
- `MongoDB Atlas`:
  - Lưu kết quả phân tích (`cv_analyses`)
  - Lưu bộ câu hỏi (`interview_questions`)
- `Redis`:
  - Lưu trạng thái session: `processing|done|failed`

## 3. Cấu trúc source code

```text
backend/
├── main.py
├── requirements.txt
├── api/
│   └── routes/
│       ├── cv.py
│       └── questions.py
├── core/
│   ├── config.py
│   ├── exceptions.py
│   └── security.py
├── db/
│   ├── mongodb.py
│   └── repositories/
│       ├── cv_repo.py
│       └── question_repo.py
├── integrations/
│   └── tinix_careerpathkg/
│       └── ...
├── models/
│   ├── career_kg.py
│   ├── cv_analysis.py
│   └── interview.py
├── prompts/
│   ├── cv_analysis.py
│   └── question_gen.py
└── services/
    ├── parser.py
    ├── analyzer.py
    ├── career_kg.py
    └── question_gen.py
```

## 4. Luồng xử lý

1. FE gọi `POST /api/cv/analyze` với file CV + thông tin JD.
2. Backend tạo `session_id`, ghi trạng thái `processing` vào Redis.
3. Background task chạy pipeline:
   - Parse CV bằng MinerU CLI.
   - Gọi Gemini để phân tích CV theo schema.
   - **Làm giàu dữ liệu bằng Knowledge Graph (KG)**:
     - Phân cụm yêu cầu JD.
     - Khớp kỹ năng từ CV với yêu cầu.
     - Xác định khoảng cách kỹ năng (skill gaps).
     - Đề xuất lộ trình nghề nghiệp.
   - Gọi Gemini để sinh bộ câu hỏi (kèm ngữ cảnh từ KG).
   - Ghi kết quả vào MongoDB Atlas (nhúng dữ liệu KG).
   - Cập nhật Redis thành `done`.
4. FE poll `GET /api/cv/{session_id}` hoặc `GET /api/questions/{session_id}`.

## 5. Mô hình dữ liệu

### `cv_analyses`

- `session_id` (unique)
- `user_id`
- `filename`, `job_title`, `job_description`, `created_at`
- Kết quả phân tích CV (score, strengths, gaps, skills_match, ...)
- `kg_enrichment`: Dữ liệu làm giàu từ Knowledge Graph.
- `model_used`
- `processing_time_ms`

### `interview_questions`

- `session_id` (unique)
- `analysis_id`
- `job_title`, `experience_level`, `created_at`
- `questions[]`:
  - `question`, `type`, `difficulty`, `target_skill`, `why_asked`, `answer...`
  - `kg_metadata`: Thông tin KG liên quan đến câu hỏi (requirement, score, severity).
- `total_questions`
- `kg_enrichment`: Bản sao dữ liệu KG tại thời điểm sinh câu hỏi.

## 6. Index MongoDB

- `cv_analyses.session_id` unique
- `cv_analyses.user_id + created_at` compound
- `cv_analyses.created_at` desc
- `interview_questions.session_id` unique
- `interview_questions.analysis_id`

## 7. Xử lý lỗi hiện tại

- Sai định dạng file: trả `400`
- Vượt quá kích thước file: trả `400`
- Session chưa có kết quả và đang xử lý: trả `202`
- Session lỗi pipeline: trả `500` kèm lý do trong Redis
- Session không tồn tại: trả `404`

## 8. Ghi chú kỹ thuật

- Pipeline dùng `BackgroundTasks` của FastAPI (không dùng Celery).
- Parse dùng lệnh CLI `mineru -p <input> -o <output> -b <backend>`.
- LLM gọi trực tiếp REST endpoint Gemini (`generateContent`).
