# Kiến trúc hệ thống

## 1. Tổng quan
`cv-module` là backend FastAPI cho ba luồng chính:

- Phân tích CV theo JD.
- Sinh câu hỏi phỏng vấn từ CV + JD hoặc chỉ từ JD.
- Đánh giá transcript phỏng vấn với context từ Knowledge Graph.

Hệ thống dùng MongoDB để lưu document kết quả, Redis để lưu trạng thái background task, MinerU để parse CV, Gemini để phân tích/sinh ngôn ngữ, và Tinix-CareerPathKG compiled artifact để làm structured Knowledge Graph runtime.

## 2. Cấu trúc mã nguồn
```text
backend/
├── api/routes/                         # HTTP endpoints: cv, questions, evaluations
├── core/                               # Config và exception
├── data/tinix_kg/career_kg.json        # Compiled Tinix KG artifact dùng lúc runtime
├── db/                                 # MongoDB connection và repositories
├── integrations/tinix_careerpathkg/    # Build/load/search Tinix KG artifact
├── models/                             # Pydantic schemas
├── prompts/                            # Prompt templates cho Gemini
├── scripts/build_tinix_kg_artifact.py  # Build artifact từ Tinix-CareerPathKG/data
├── services/                           # Business logic
├── tests/                              # Unit tests cho Tinix KG và evaluation context
├── main.py
└── requirements.txt
```

`integrations/career_rag` đã bị loại bỏ. Runtime không cần vector store để tạo KG.

## 3. Pipeline CV analysis
Khi client gọi `POST /api/cv/analyze`:

1. API validate file PDF/DOCX, `job_title`, `job_description`, `experience_level`, `num_questions`.
2. Tạo `session_id`, ghi status `processing` vào Redis, trả về `202 Accepted`.
3. Background task parse CV bằng MinerU thành Markdown.
4. Gemini analyzer tạo `CVAnalysisPayload`: score, strengths, gaps, skills matched/missing.
5. `build_career_kg_enrichment()` load Tinix artifact và thực hiện downstream task `cv_jd_matching`.
6. Question generator nhận `question_targets` từ KG để sinh câu hỏi có mục tiêu rõ ràng.
7. Câu hỏi được bổ sung metadata KG bằng `enrich_questions_with_kg_metadata()`.
8. Lưu CV analysis và questions vào MongoDB, cập nhật Redis thành `done`.

## 4. Pipeline job-only questions
Khi client gọi `POST /api/questions/from-job`:

1. Hệ thống tách requirements từ JD.
2. `build_job_kg_enrichment()` lookup requirements trong Tinix KG artifact.
3. Sinh `requirement_clusters`, `skill_gaps`, `question_targets`.
4. Gemini sinh câu hỏi theo target do KG chọn.
5. Lưu document vào `interview_questions` với `source: "job_only"`.

Luồng này không cần CV. Tất cả requirements trong JD được xem là nội dung cần kiểm chứng khi phỏng vấn.

## 5. Pipeline evaluation
Khi client gọi `POST /api/evaluations`:

1. API validate transcript có ít nhất một câu trả lời của ứng viên.
2. Nếu có `question_session_id`, `load_evaluation_kg_context()` đọc questions + `kg_enrichment` từ MongoDB.
3. Evaluation prompt nhận context theo từng câu hỏi:
   - requirement cần kiểm chứng;
   - expected evidence;
   - gap severity;
   - priority;
   - related skills.
4. Gemini chấm theo STAR và đối chiếu câu trả lời với KG context.
5. Lưu evaluation document vào MongoDB.

## 6. Tinix Knowledge Graph runtime
Nguồn dữ liệu canonical là:

```text
Tinix-CareerPathKG/data/req_skill_matching.jsonl
Tinix-CareerPathKG/data/req_sum.jsonl
```

Runtime không đọc trực tiếp hai file JSONL này. Script build sẽ compile thành:

```text
backend/data/tinix_kg/career_kg.json
```

Artifact này đã là structured KG dạng JSON, gồm:

- `nodes`: `Requirement`, `Skill`, `Domain`, `Cluster`.
- `edges`: `MATCHES`, `NOT_MATCH`, `RELATED_TO`, `BELONGS_TO_DOMAIN`.
- `requirements`: lookup table cho requirement enrichment.
- `skills`: normalized skill table.
- `pair_labels`: Tinix label cho requirement-skill pairs sau deduplicate.

Chi tiết xem [knowledge_graph.md](knowledge_graph.md).

## 7. Fallback modes
`KG_MODE` hỗ trợ các giá trị:

- `disabled`: tắt KG enrichment.
- `auto`: ưu tiên Tinix artifact; nếu artifact thiếu/lỗi thì fallback về heuristic.
- `graph`: ưu tiên graph artifact; nếu graph enrichment lỗi trong runtime thì fallback heuristic để API không fail.
- `heuristic`: bỏ qua artifact, dùng rule/text similarity.
- `model`: dùng wrapper Tinix/Gemini cũ nếu có API key.

Hướng chính hiện tại là `auto` với artifact `career_kg.json`.

## 8. MongoDB collections
### `cv_analyses`
Lưu kết quả phân tích CV:

- `session_id`, `user_id`, `filename`.
- `job_title`, `job_description`, `experience_level`.
- `overall_match_score`, `strengths`, `gaps`, `skills_match`.
- `kg_enrichment`.

### `interview_questions`
Lưu bộ câu hỏi:

- `session_id`, `analysis_id`, `source`.
- `job_title`, `job_description`, `experience_level`.
- `questions[]` với `kg_requirement`, `kg_match_score`, `kg_gap_severity`, `kg_priority`.
- `kg_enrichment`.

### `evaluations`
Lưu kết quả chấm transcript:

- `session_id`, `question_session_id`, `interview_session_id`.
- `transcript`.
- `questions[]` STAR score.
- `overall`.
- `kg_context_used`, `kg_enrichment`.
