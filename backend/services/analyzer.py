import asyncio
import json
from typing import Any

import httpx
from pydantic import ValidationError

from core.config import get_settings
from models.cv_analysis import CVAnalysisPayload
from prompts.cv_analysis import CV_ANALYSIS_SYSTEM_PROMPT, build_cv_analysis_user_prompt


class CVAnalyzerError(Exception):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")

    return json.loads(stripped[start : end + 1])


async def _call_gemini(system_prompt: str, user_prompt: str, timeout_seconds: int) -> str:
    settings = get_settings()
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "text/plain",
        },
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(endpoint, json=payload)
        response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise CVAnalyzerError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise CVAnalyzerError("Gemini returned empty content")
    return text


async def analyze_cv(
    *,
    cv_markdown: str,
    job_title: str,
    job_description: str,
    experience_level: str,
    target_language: str = "en",
) -> CVAnalysisPayload:
    user_prompt = build_cv_analysis_user_prompt(
        job_title=job_title,
        experience_level=experience_level,
        job_description=job_description,
        cv_markdown=cv_markdown,
        target_language=target_language,
    )

    last_error: Exception | None = None
    repair_instruction = (
        "Return only valid JSON matching the schema exactly. "
        "Do not include markdown or any explanation."
    )

    for attempt in range(3):
        try:
            prompt = user_prompt if attempt == 0 else f"{user_prompt}\n\n{repair_instruction}"
            raw = await _call_gemini(CV_ANALYSIS_SYSTEM_PROMPT, prompt, timeout_seconds=30)
            data = _extract_json(raw)
            return CVAnalysisPayload.model_validate(data)
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise CVAnalyzerError("Gemini timeout while analyzing CV") from exc
        except httpx.HTTPStatusError as exc:
            raise CVAnalyzerError(f"Gemini HTTP error: {exc.response.status_code}") from exc
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            continue
        except Exception as exc:
            raise CVAnalyzerError("Failed to analyze CV") from exc

    raise CVAnalyzerError(f"Gemini returned invalid analysis JSON after retries: {last_error}")
