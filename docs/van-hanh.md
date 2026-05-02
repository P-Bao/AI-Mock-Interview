# Hướng dẫn cài đặt và vận hành

## 1. Yêu cầu

- Python 3.11+ (đang chạy tốt với 3.13)
- Redis
- MongoDB Atlas connection string
- Quyền truy cập Gemini API

## 2. Tạo môi trường và cài dependency

Từ thư mục gốc project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install uv
uv pip install -U "mineru[all]"
python -m pip install -r backend\requirements.txt
```

Kiểm tra MinerU:

```powershell
.\.venv\Scripts\mineru --help
```

## 3. Cấu hình môi trường

Tạo file `backend/.env` từ `backend/.env.example` và điền giá trị thật:

```env
MONGODB_ATLAS_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/
MONGODB_DB_NAME=cv_interview_app

GEMINI_API_KEY=<your_api_key>
GEMINI_MODEL=gemini-3.1-flash-lite

REDIS_URL=redis://localhost:6379

MINERU_MODEL_SOURCE=huggingface
MINERU_BACKEND=pipeline

# Knowledge Graph (KG)
KG_ENABLED=true
KG_MODE=auto
KG_TIMEOUT_SECONDS=10

MAX_FILE_SIZE_MB=10
MAX_QUESTIONS=20
TASK_TTL_SECONDS=3600
```

Ghi chú:

- `GEMINI_API_KEY` là bắt buộc.
- `MINERU_BACKEND=pipeline` phù hợp máy không có GPU đủ mạnh.

## 4. Chạy backend local

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```powershell
curl http://localhost:8000/health
```

## 5. Chạy bằng Docker Compose

Project có `docker-compose.yml` cho:

- `backend`
- `redis`

MongoDB dùng Atlas nên không có service Mongo local trong compose.

```powershell
docker compose up --build
```

## 6. Kiểm tra nhanh bằng compile

```powershell
.\.venv\Scripts\python -m compileall backend
```

## 7. Gợi ý vận hành production

- Đặt reverse proxy (Nginx/Caddy) phía trước FastAPI.
- Bật logging tập trung cho lỗi parse/LLM/Mongo.
- Tách background processing chuyên dụng (Celery/RQ) nếu tải tăng cao.
- Quản lý secret bằng secret manager thay vì file `.env` trên server.
