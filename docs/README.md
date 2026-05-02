# Tài liệu Backend CV Module

Thư mục `docs/` chứa tài liệu tiếng Việt cho module phân tích CV và sinh câu hỏi phỏng vấn.

## Danh sách tài liệu

- `docs/kien-truc.md`: Mô tả kiến trúc hệ thống, luồng xử lý, thành phần chính và tích hợp Knowledge Graph.
- `docs/api.md`: Đặc tả API, request/response mẫu (bao gồm dữ liệu làm giàu từ KG).
- `docs/van-hanh.md`: Hướng dẫn cài đặt, cấu hình `.env`, chạy local bằng `venv`, kiểm tra nhanh.

## Phạm vi

Tài liệu phản ánh trạng thái code hiện tại trong thư mục `backend/`:

- Web framework: FastAPI
- Parse CV: MinerU CLI
- LLM: Gemini qua REST API (khóa `GEMINI_API_KEY`)
- Database: MongoDB Atlas (Motor async)
- Trạng thái tác vụ: Redis
- Knowledge Graph (KG): Tích hợp Tinix-CareerPathKG để làm giàu dữ liệu kỹ năng, khoảng cách kỹ năng (skill gaps) và định hướng nghề nghiệp.
