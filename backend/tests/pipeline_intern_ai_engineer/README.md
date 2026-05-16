# Intern AI Engineer API Pipeline Scenario

This folder contains manual scripts for exercising the live FastAPI backend with the Intern AI Engineer CV/JD scenario. The scripts do not pass `target_language`; the backend detects the language from the JD and question/evaluation context.

## Prerequisites

Start the backend stack from `cv-module`:

```powershell
docker compose up --build
```

Wait until the backend is ready at:

```text
http://127.0.0.1:8000/ready
```

The scripts default to `http://127.0.0.1:8000`. Override it with `CV_PIPELINE_BASE_URL` if needed.

The host Python environment must have the backend dependencies installed, including `httpx`.

## Step 1: CV Analysis And Questions

Run from `cv-module`:

```powershell
python backend/tests/pipeline_intern_ai_engineer/run_cv_question_pipeline.py
```

This script reads `manifest.json`, uploads `graduate-artificial-intelligence-engineer-resume-example.pdf` and `job_description.txt` to `POST /api/cv/analyze`, then polls:

- `GET /api/cv/{session_id}`
- `GET /api/questions/{session_id}`

Outputs are written to:

- `output/cv_analysis.json`
- `output/questions.json`
- `output/session.json`

## Step 2: Evaluation

Run this only after step 1 has created `output/session.json` and the files in `transcripts/*.json` contain interview transcript data.

Run from `cv-module`:

```powershell
python backend/tests/pipeline_intern_ai_engineer/run_evaluation_pipeline.py
```

Each transcript must be either a JSON list of entries or an object with an `interview` or `transcript` list. Each entry must contain:

```json
{
  "role": "user",
  "text": "answer text"
}
```

Allowed roles are `user` and `model`.

The script sends each transcript to `POST /api/evaluations`, polls `GET /api/evaluations/{session_id}`, and does not send `target_language`.

Outputs are written to:

- `output/evaluations/<transcript-name>.json`
- `output/evaluation_summary.json`

## Files

- `manifest.json`: scenario settings, resume path, JD path, question count, and score thresholds.
- `job_description.txt`: English JD used by the backend for language detection.
- `graduate-artificial-intelligence-engineer-resume-example.pdf`: resume uploaded in step 1.
- `transcripts/*.json`: manual interview transcripts for step 2.
- `output/`: generated pipeline output.
