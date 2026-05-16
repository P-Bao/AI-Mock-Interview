# Module phân tích CV và sinh câu hỏi phỏng vấn (AI-powered)

Đây là Backend Module cốt lõi chịu trách nhiệm tự động hóa quy trình tuyển dụng. Hệ thống nhận đầu vào là file CV (PDF/DOCX) và mô tả công việc (JD), sau đó sử dụng trí tuệ nhân tạo (Gemini) kết hợp với Knowledge Graph để phân tích mức độ phù hợp và tự động sinh ra bộ câu hỏi phỏng vấn kỹ thuật.

## Tính năng nổi bật
- **Trích xuất dữ liệu (OCR/parsing):** Chuyển đổi chính xác CV định dạng PDF/DOCX (kể cả dạng ảnh) sang văn bản Markdown bằng công cụ **MinerU**.
- **Phân tích bằng AI:** Đánh giá CV sâu sắc bằng **Gemini 1.5 Flash/3.1 Flash Lite Preview**, nhận diện điểm mạnh, điểm yếu và kinh nghiệm.
- **Tích hợp Knowledge Graph (KG):** Làm giàu dữ liệu kỹ năng dựa trên **[Tinix-CareerPathKG](https://github.com/lengocquanggit255/Tinix-CareerPathKG)**, phát hiện "khoảng trống kỹ năng" (skill gaps) một cách có cơ sở.
- **Sinh câu hỏi phỏng vấn cá nhân hóa:** Tự động tạo câu hỏi bao quát từ kiến thức nền tảng đến thiết kế hệ thống, tùy chỉnh theo 6 cấp độ (intern, fresher, junior, mid, senior, lead).
- **Kiến trúc bất đồng bộ (Async):** Tối ưu hiệu năng cao với FastAPI, MongoDB (Motor) và Redis task queue.

## Tài liệu hướng dẫn
Để hiểu rõ hơn về dự án và cách triển khai, vui lòng đọc các tài liệu chi tiết trong thư mục `docs/`:

1. **[Kiến trúc hệ thống (Architecture)](docs/architecture.md):** Luồng hoạt động, cấu trúc mã nguồn, và chi tiết cách Knowledge Graph được áp dụng.
2. **[Đặc tả API (API reference)](docs/api.md):** Danh sách các endpoints, định dạng request/response (JSON) và các mã lỗi.
3. **[Hướng dẫn vận hành (Deployment)](docs/deployment.md):** Cách cấu hình biến môi trường `.env`, cài đặt Docker, xử lý lỗi thường gặp.
4. **[Tinix Knowledge Graph](docs/knowledge_graph.md):** Source data, runtime artifact `career_kg.json`, schema, build script và downstream tasks.
