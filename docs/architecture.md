# Kiến trúc hệ thống

## 1. Tổng quan kiến trúc
Hệ thống được thiết kế theo kiến trúc **Microservices-ready**, sử dụng **FastAPI** làm web framework chính, **MongoDB** để lưu trữ tài liệu (NoSQL), và **Redis** để quản lý trạng thái các tác vụ xử lý nền (Background tasks). Quy trình phân tích nặng (parse PDF, gọi API LLM) được tách biệt khỏi main thread để đảm bảo API luôn phản hồi nhanh chóng.

## 2. Cấu trúc mã nguồn
```text
backend/
├── api/routes/           # Định nghĩa các HTTP endpoints (cv.py, questions.py)
├── core/                 # Cấu hình môi trường (config.py), xử lý lỗi (exceptions.py)
├── db/                   # Kết nối MongoDB và Repository pattern thao tác với CSDL
├── integrations/         # Các module tích hợp bên thứ 3 (Tinix-CareerPathKG)
├── models/               # Pydantic schemas (cv_analysis.py, interview.py, career_kg.py)
├── prompts/              # Các system prompts và user prompts cho AI
├── services/             # Chứa logic nghiệp vụ chính (analyzer.py, parser.py, question_gen.py)
├── main.py               # Entry point của ứng dụng FastAPI
└── requirements.txt      # Khai báo thư viện Python
```

## 3. Luồng xử lý (pipeline) chi tiết
Khi client gọi API `POST /api/cv/analyze`:
1. **Tiếp nhận và xác thực:** FastAPI nhận file (PDF/DOCX), kiểm tra dung lượng và các tham số (job title, experience level...).
2. **Khởi tạo task:** Hệ thống tạo một `session_id` (UUID), lưu trạng thái `processing` vào Redis và trả về phản hồi `202 Accepted` ngay lập tức.
3. **Xử lý nền (Background task):**
   - **Parser (MinerU):** Chuyển đổi file CV thành văn bản Markdown. Nếu gặp file phức tạp, MinerU có timeout an toàn (mặc định 300s).
   - **Analyzer (Gemini):** Gửi Markdown CV và JD tới Gemini để lấy đánh giá tổng quan (điểm số, điểm mạnh, điểm yếu).
   - **Knowledge Graph enrichment:** Dữ liệu được đưa qua module KG để tinh chỉnh (xem chi tiết mục 4).
   - **Question generator:** Sinh câu hỏi phỏng vấn dựa trên điểm yếu (skill gaps) do KG và AI phát hiện, độ khó tùy biến theo 6 cấp độ kinh nghiệm.
4. **Lưu trữ:** Lưu toàn bộ document vào MongoDB.
5. **Hoàn tất:** Cập nhật Redis thành `done`. Client dùng `session_id` gọi API GET để nhận kết quả.

## 4. Tích hợp Knowledge Graph (Tinix-CareerPathKG)
Dự án ứng dụng các kỹ thuật từ repository **[Tinix-CareerPathKG](https://github.com/lengocquanggit255/Tinix-CareerPathKG)** để giảm thiểu ảo giác (hallucination) của LLM và cung cấp lý do rõ ràng cho các câu hỏi phỏng vấn.

### Các downstream tasks được áp dụng:
1. **Requirement summarization (Tóm tắt yêu cầu):** Hệ thống không dùng toàn bộ text JD tĩnh. Thay vào đó, nó nhóm các yêu cầu từ JD thành các "cluster" (ví dụ: Backend, Database, Cloud) cùng với trọng số (weight) để đánh giá tầm quan trọng.
2. **Skill matching (Khớp kỹ năng):** Đánh giá các kỹ năng ứng viên có trong CV so với các clusters yêu cầu. Phân loại mối quan hệ rõ ràng: `exact` (khớp hoàn toàn), `related` (liên quan), `missing` (thiếu).
3. **Gap analysis (Phân tích khoảng trống):** Dựa trên skill matching, hệ thống xác định chính xác ứng viên đang thiếu kỹ năng cốt lõi nào và đánh giá mức độ nghiêm trọng (`critical`, `moderate`, `minor`), từ đó đưa ra `recommendation`.
4. **Career guidance (Định hướng nghề nghiệp):** (Mở rộng trong tương lai) Đề xuất lộ trình học tập dựa trên sự thiếu hụt kỹ năng và định hướng phát triển từ Graph.

Dữ liệu này được tổng hợp trong cấu trúc `kg_enrichment` và nhúng thẳng vào dữ liệu của từng câu hỏi (`kg_metadata`), giúp người phỏng vấn biết *tại sao* hệ thống lại sinh ra câu hỏi đó.

## 5. Mô hình dữ liệu (MongoDB)

### Collection `cv_analyses`
Lưu trữ thông tin phân tích CV cơ bản và dữ liệu làm giàu từ KG.
- `session_id`: UUID định danh phiên.
- `job_title`, `job_description`, `experience_level`.
- `overall_match_score`, `strengths`, `gaps`.
- `kg_enrichment`: Dữ liệu phân cụm, mapping kỹ năng và skill gaps từ KG.

### Collection `interview_questions`
Lưu trữ bộ câu hỏi sinh ra.
- `session_id`, `analysis_id` (liên kết với cv_analyses).
- `experience_level`: `intern`, `fresher`, `junior`, `mid`, `senior`, `lead`.
- `questions[]`: Danh sách các câu hỏi.
  - Mỗi câu hỏi gồm: `question`, `type`, `difficulty`, `target_skill`, `why_asked`.
  - Kèm theo `kg_metadata`: Liên kết trực tiếp tới kỹ năng trong KG đang bị hổng và độ nghiêm trọng (gap severity).
