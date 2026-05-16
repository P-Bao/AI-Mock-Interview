from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx


SCENARIO_DIR = Path(__file__).resolve().parent
TRANSCRIPTS_DIR = SCENARIO_DIR / "transcripts"
OUTPUT_DIR = SCENARIO_DIR / "output"
EVALUATIONS_DIR = OUTPUT_DIR / "evaluations"
BASE_URL = os.getenv("CV_PIPELINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
READY_TIMEOUT_SECONDS = int(os.getenv("CV_PIPELINE_READY_TIMEOUT_SECONDS", "120"))
POLL_TIMEOUT_SECONDS = int(os.getenv("CV_PIPELINE_POLL_TIMEOUT_SECONDS", "900"))
POLL_INTERVAL_SECONDS = float(os.getenv("CV_PIPELINE_POLL_INTERVAL_SECONDS", "3"))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def wait_until_ready(client: httpx.Client) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    last_error = ""

    while time.monotonic() < deadline:
        try:
            response = client.get("/ready")
            if response.status_code == 200 and response.json().get("ready") is True:
                return
            last_error = f"HTTP {response.status_code}: {response.text}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Backend is not ready at {BASE_URL}/ready. Last error: {last_error}")


def poll_json(client: httpx.Client, path: str, *, label: str) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        response = client.get(path)
        if response.status_code == 202:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        if response.status_code >= 400:
            raise RuntimeError(f"{label} failed with HTTP {response.status_code}: {response.text}")
        return response.json()

    raise TimeoutError(f"Timed out waiting for {label} from {path}")


def load_interview(path: Path) -> list[dict[str, str]]:
    if path.stat().st_size == 0:
        raise ValueError(f"Transcript file is empty: {path}")

    payload = read_json(path)
    if isinstance(payload, list):
        interview = payload
    elif isinstance(payload, dict):
        interview = payload.get("interview") or payload.get("transcript")
    else:
        interview = None

    if not isinstance(interview, list):
        raise ValueError(f"Transcript must be a JSON list or an object with interview/transcript: {path}")

    for index, item in enumerate(interview):
        if not isinstance(item, dict) or item.get("role") not in {"user", "model"} or not isinstance(item.get("text"), str):
            raise ValueError(f"Invalid transcript entry at {path}:{index}; expected role and text")

    return interview


def summarize_evaluation(name: str, session_id: str, evaluation: dict[str, Any]) -> dict[str, Any]:
    overall = evaluation.get("overall") or {}
    return {
        "name": name,
        "session_id": session_id,
        "overall_score": overall.get("overall_score"),
        "total_questions": evaluation.get("total_questions"),
        "target_language": evaluation.get("target_language"),
        "kg_context_used": evaluation.get("kg_context_used"),
        "language_policy_failed": evaluation.get("language_policy_failed"),
        "output_path": str(EVALUATIONS_DIR / f"{name}.json"),
    }


def main() -> int:
    session_path = OUTPUT_DIR / "session.json"
    if not session_path.is_file():
        raise FileNotFoundError(
            f"Missing {session_path}. Run run_cv_question_pipeline.py successfully before evaluations."
        )

    transcript_paths = sorted(TRANSCRIPTS_DIR.glob("*.json"))
    if not transcript_paths:
        raise FileNotFoundError(f"No transcript JSON files found in {TRANSCRIPTS_DIR}")

    session = read_json(session_path)
    question_session_id = session["question_session_id"]
    cv_session_id = session["cv_session_id"]
    EVALUATIONS_DIR.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, Any]] = []
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        wait_until_ready(client)

        for transcript_path in transcript_paths:
            name = transcript_path.stem
            interview = load_interview(transcript_path)
            response = client.post(
                "/api/evaluations",
                json={
                    "interview": interview,
                    "interview_session_id": name,
                    "question_session_id": question_session_id,
                    "cv_session_id": cv_session_id,
                },
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Evaluation request for {transcript_path.name} failed with "
                    f"HTTP {response.status_code}: {response.text}"
                )

            accepted = response.json()
            evaluation_session_id = accepted["session_id"]
            evaluation = poll_json(
                client,
                f"/api/evaluations/{evaluation_session_id}",
                label=f"evaluation {transcript_path.name}",
            )
            write_json(EVALUATIONS_DIR / f"{name}.json", evaluation)
            summaries.append(summarize_evaluation(name, evaluation_session_id, evaluation))

    summary = {
        "scenario": session.get("scenario"),
        "base_url": BASE_URL,
        "cv_session_id": cv_session_id,
        "question_session_id": question_session_id,
        "evaluations": summaries,
    }
    write_json(OUTPUT_DIR / "evaluation_summary.json", summary)

    print(f"Evaluation files written to {EVALUATIONS_DIR}")
    print(f"Summary written to {OUTPUT_DIR / 'evaluation_summary.json'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
