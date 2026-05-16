from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx


SCENARIO_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCENARIO_DIR / "output"
BASE_URL = os.getenv("CV_PIPELINE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
READY_TIMEOUT_SECONDS = int(os.getenv("CV_PIPELINE_READY_TIMEOUT_SECONDS", "120"))
POLL_TIMEOUT_SECONDS = int(os.getenv("CV_PIPELINE_POLL_TIMEOUT_SECONDS", "900"))
POLL_INTERVAL_SECONDS = float(os.getenv("CV_PIPELINE_POLL_INTERVAL_SECONDS", "3"))


def read_json(path: Path) -> dict[str, Any]:
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


def main() -> int:
    manifest = read_json(SCENARIO_DIR / "manifest.json")
    resume_path = SCENARIO_DIR / manifest["resume_path"]
    jd_path = SCENARIO_DIR / manifest["job_description_path"]

    if not resume_path.is_file():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")
    if not jd_path.is_file():
        raise FileNotFoundError(f"Job description file not found: {jd_path}")

    job_description = jd_path.read_text(encoding="utf-8")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        wait_until_ready(client)

        with resume_path.open("rb") as resume_file:
            response = client.post(
                "/api/cv/analyze",
                data={
                    "job_title": manifest["job_title"],
                    "job_description": job_description,
                    "experience_level": manifest["experience_level"],
                    "num_questions": str(manifest.get("num_questions", 10)),
                },
                files={
                    "file": (
                        resume_path.name,
                        resume_file,
                        "application/pdf",
                    )
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(f"CV analyze request failed with HTTP {response.status_code}: {response.text}")

        accepted = response.json()
        session_id = accepted["session_id"]
        cv_analysis = poll_json(client, f"/api/cv/{session_id}", label="CV analysis")
        questions = poll_json(client, f"/api/questions/{session_id}", label="questions")

    session = {
        "scenario": manifest.get("scenario"),
        "base_url": BASE_URL,
        "session_id": session_id,
        "cv_session_id": session_id,
        "question_session_id": session_id,
        "job_title": manifest["job_title"],
        "experience_level": manifest["experience_level"],
        "num_questions": manifest.get("num_questions", 10),
        "resume_path": str(resume_path),
        "job_description_path": str(jd_path),
        "accepted_response": accepted,
    }

    write_json(OUTPUT_DIR / "cv_analysis.json", cv_analysis)
    write_json(OUTPUT_DIR / "questions.json", questions)
    write_json(OUTPUT_DIR / "session.json", session)

    print(f"CV analysis written to {OUTPUT_DIR / 'cv_analysis.json'}")
    print(f"Questions written to {OUTPUT_DIR / 'questions.json'}")
    print(f"Session context written to {OUTPUT_DIR / 'session.json'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
