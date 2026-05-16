# Tinix Knowledge Graph

## 1. Mục đích
`cv-module` dùng Tinix-CareerPathKG như structured Knowledge Graph cho các downstream tasks:

- `cv_jd_matching`: đối chiếu CV skills với JD requirements.
- `question_planning`: chọn requirement/skill nên hỏi, priority, difficulty, lý do hỏi.
- `answer_evaluation_context`: tạo context cho evaluation theo từng câu hỏi.

Hệ thống không dùng `integrations/career_rag` và không cần vector/RAG ingestion để có Knowledge Graph.

## 2. Source data và runtime artifact
Source data canonical nằm ngoài module:

```text
Tinix-CareerPathKG/data/req_skill_matching.jsonl
Tinix-CareerPathKG/data/req_sum.jsonl
```

Runtime artifact nằm trong backend:

```text
cv-module/backend/data/tinix_kg/career_kg.json
```

`career_kg.json` là compiled artifact. Nếu source data thay đổi, phải build lại artifact.

## 3. Build artifact
Chạy từ `cv-module/backend`:

```powershell
..\.venv\Scripts\python.exe scripts\build_tinix_kg_artifact.py
```

Có thể chỉ định source/output khác:

```powershell
..\.venv\Scripts\python.exe scripts\build_tinix_kg_artifact.py --data-dir ..\..\Tinix-CareerPathKG\data --output-dir .\data\tinix_kg
```

Script sẽ:

- Đọc `req_skill_matching.jsonl`.
- Đọc `req_sum.jsonl`.
- Normalize và deduplicate requirement-skill pairs.
- Tạo nodes và edges deterministic.
- Ghi `career_kg.json`.

## 4. Artifact schema
Top-level fields:

```json
{
  "version": "tinix-kg-json-v1",
  "source": "Tinix-CareerPathKG/data",
  "counts": {},
  "nodes": [],
  "edges": [],
  "requirements": [],
  "skills": [],
  "pair_labels": {}
}
```

Node types:

- `Requirement`
- `Skill`
- `Domain`
- `Cluster`

Edge types:

- `MATCHES`: Tinix label `1` cho requirement-skill pair.
- `NOT_MATCH`: Tinix label `0`.
- `RELATED_TO`: requirement liên quan cluster.
- `BELONGS_TO_DOMAIN`: requirement thuộc domain.

Runtime lookup chủ yếu dùng `requirements` và `pair_labels`; `nodes`/`edges` giữ graph representation để audit và mở rộng sau này.

## 5. Runtime selection
`services/career_kg.py` load artifact bằng `TinixCareerKGStore`.

Với `KG_MODE=auto`:

1. Nếu artifact tồn tại: dùng graph enrichment.
2. Nếu artifact thiếu/lỗi: fallback heuristic.

Với `KG_MODE=graph`:

1. Ưu tiên graph artifact.
2. Nếu graph build/enrichment lỗi trong runtime, fallback heuristic để API không fail.

Với `KG_MODE=heuristic`: bỏ qua artifact.

Với `KG_MODE=disabled`: tắt KG.

## 6. Output KG payload
`KGEnrichmentPayload` gồm:

- `requirement_clusters`: nhóm requirements theo domain/cluster, có `evidence`.
- `skill_matches`: requirement -> CV skill, score, relation, evidence.
- `skill_gaps`: requirement thiếu, severity, priority, recommendation.
- `question_targets`: danh sách target để question generator ưu tiên.
- `career_guidance`: recommendations ngắn gọn dựa trên gaps.
- `confidence`: tỷ lệ requirements được match exact/related.

Questions sau khi enrich có thêm:

- `kg_requirement`
- `kg_match_score`
- `kg_gap_severity`
- `kg_priority`

## 7. Evaluation context
`services/evaluation_kg.py` đọc `question_session_id` và tạo context cho prompt evaluation:

- requirement cần kiểm chứng;
- related skill;
- expected evidence từ Tinix;
- gap severity;
- priority;
- why_asked.

KG context chỉ là nền đối chiếu. Evaluation prompt vẫn phải chấm dựa trên transcript, không lấy KG làm bằng chứng thay câu trả lời.

## 8. Khi nào cần source data Tinix
Cần `Tinix-CareerPathKG/data` khi:

- build artifact lần đầu;
- rebuild sau khi source data thay đổi;
- audit normalization/dedup;
- thay đổi graph schema.

Không cần đọc source data trong runtime nếu `career_kg.json` đã tồn tại và hợp lệ.
