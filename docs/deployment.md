# Hướng dẫn triển khai và vận hành (Deployment)

Tài liệu này hướng dẫn cách thiết lập môi trường, chạy ứng dụng bằng Docker Compose hoặc local, và xử lý các lỗi thường gặp.

## 1. Yêu cầu hệ thống (Prerequisites)
- **Docker và Docker Compose** (khuyên dùng)
- Hoặc môi trường local:
  - Python 3.11+
  - Redis server đang chạy.
  - Trình biên dịch C++ (dùng để cài đặt module Python của MinerU nếu cần).

## 2. Cấu hình môi trường (.env)
Bắt buộc phải có file `.env` tại thư mục `backend/`. Copy từ `backend/.env.example`:

```env
# MongoDB Atlas (Nên dùng DB cloud để dễ quản lý)
MONGODB_ATLAS_URI=mongodb+srv://<user>:<pass>@cluster...
MONGODB_DB_NAME=cv_interview_app

# Gemini API (Lấy từ Google AI Studio)
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.1-flash-lite-preview

# Redis (Dùng nội bộ trong Docker thì trỏ tới tên service 'redis')
REDIS_URL=redis://redis:6379

# Cấu hình MinerU (Công cụ parse PDF)
MINERU_MODEL_SOURCE=huggingface
MINERU_BACKEND=pipeline
MINERU_TIMEOUT_SECONDS=300 # Cho phép xử lý PDF nặng tối đa 5 phút
MINERU_WARMUP_ENABLED=true

# Cấu hình Knowledge Graph
KG_ENABLED=true
KG_MODE=auto
KG_ARTIFACT_DIR=./data/tinix_kg
KG_TIMEOUT_SECONDS=10

# Giới hạn hệ thống
MAX_FILE_SIZE_MB=10
MAX_QUESTIONS=20
TASK_TTL_SECONDS=3600
EVAL_MAX_RETRIES=3
EVAL_TIMEOUT_SECONDS=90
```

## 3. Knowledge Graph artifact
Runtime dùng artifact:

```text
backend/data/tinix_kg/career_kg.json
```

File này được build từ source data:

```text
../Tinix-CareerPathKG/data/req_skill_matching.jsonl
../Tinix-CareerPathKG/data/req_sum.jsonl
```

Nếu artifact đã tồn tại và deploy kèm backend thì không cần chạy thêm ingestion/RAG. Nếu source data thay đổi hoặc artifact bị xoá, build lại:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts\build_tinix_kg_artifact.py
```

Kiểm tra nhanh artifact parse được:

```powershell
cd backend
..\.venv\Scripts\python.exe -c "import json; from pathlib import Path; p=Path('data/tinix_kg/career_kg.json'); d=json.load(p.open(encoding='utf-8')); print(d['version'], d['counts'])"
```

## 4. Khởi chạy hệ thống

### Cách 1: Sử dụng Docker Compose (khuyên dùng)
Hệ thống đã được đóng gói sẵn. Lệnh này sẽ dựng 2 containers: `backend` (FastAPI) và `redis` (Cache/Queue).
```bash
docker compose up -d --build
```
Kiểm tra log để đảm bảo không có lỗi:
```bash
docker compose logs -f backend
```

### Cách 2: Chạy môi trường ảo (Local)
Thích hợp cho việc dev/debug:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install uv
uv pip install -U "mineru[all]"
python -m pip install -r backend\requirements.txt

# Sửa lại file .env: REDIS_URL=redis://localhost:6379
# (Nhớ bật service Redis ở dưới local)

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 5. Xử lý các lỗi thường gặp (Troubleshooting)

### Lỗi: `ConnectionRefusedError: [Errno 111] connecting to localhost:6379`
- **Nguyên nhân:** Container backend không tìm thấy Redis ở `localhost`.
- **Cách sửa:** Trong môi trường Docker Compose, sửa file `.env`: `REDIS_URL=redis://redis:6379`. Chạy lại `docker compose up -d`.

### Lỗi: `parser_timeout` (Task bị hủy giữa chừng)
- **Nguyên nhân:** File CV PDF dạng ảnh quá nặng, MinerU cần nhiều thời gian/RAM để OCR.
- **Cách sửa:**
  - Tăng cấu hình RAM trong Docker Desktop (tối thiểu 4GB, khuyên dùng 8GB).
  - Đảm bảo biến `MINERU_TIMEOUT_SECONDS=300` trong file `.env`.

### Lỗi: `Gemini HTTP error: 404`
- **Nguyên nhân:** Tên model Gemini không tồn tại hoặc không được hỗ trợ.
- **Cách sửa:** Cập nhật biến `GEMINI_MODEL=gemini-3.1-flash-lite-preview` trong `.env`. Chạy lại `docker compose up -d`.

### Lỗi: KG trả về `heuristic` thay vì `tinix-kg-json-v1:*`
- **Nguyên nhân:** Không tìm thấy hoặc không parse được `career_kg.json`.
- **Cách sửa:**
  - Kiểm tra `KG_ARTIFACT_DIR=./data/tinix_kg`.
  - Đảm bảo file `backend/data/tinix_kg/career_kg.json` tồn tại.
  - Chạy lại script `scripts/build_tinix_kg_artifact.py`.

### Lỗi: Không còn module `integrations.career_rag`
- **Nguyên nhân:** Code cũ hoặc script cũ vẫn import module KG đã bị loại bỏ.
- **Cách sửa:** Runtime hiện tại không dùng `career_rag`. Xoá import cũ và dùng `integrations.tinix_careerpathkg.kg_store.TinixCareerKGStore` hoặc service `services.career_kg`.
