import asyncio
import json
from typing import Any

import httpx
from pydantic import ValidationError

from core.config import get_settings
from models.evaluation import EvaluationPayload
from prompts.evaluation import EVALUATION_SYSTEM_PROMPT
from services.language_guard import LanguageMismatchError, SupportedLanguage, validate_evaluation_language


class EvaluationError(Exception):
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


async def _call_gemini(payload: dict[str, Any], timeout_seconds: int) -> str:
    settings = get_settings()
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    request_payload = {
        "system_instruction": {"parts": [{"text": EVALUATION_SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "topP": 0.8,
            "maxOutputTokens": 4096,
            "responseMimeType": "application/json",
        },
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(endpoint, json=request_payload)
        response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise EvaluationError("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise EvaluationError("Gemini returned empty content")
    return text


async def evaluate_interview(
    *,
    transcript: list[dict[str, str]],
    kg_context: str | None = None,
    target_language: SupportedLanguage = "en",
    timeout_seconds: int = 90,
) -> EvaluationPayload:
    settings = get_settings()
    retries = max(settings.eval_max_retries, 1)

    base_payload: dict[str, Any] = {"interview": transcript, "target_language": target_language}
    if kg_context:
        base_payload["kg_context"] = kg_context

    repair_instruction = (
        "Return only valid JSON matching schema. "
        "No markdown, no explanation, and ensure numeric ranges are respected."
    )
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            payload = base_payload if attempt == 0 else {**base_payload, "repair_instruction": repair_instruction}
            raw = await _call_gemini(payload, timeout_seconds=timeout_seconds)
            if not raw.strip():
                raise EvaluationError("Gemini returned empty content")
            data = _extract_json(raw)
            payload = EvaluationPayload.model_validate(data)
            validate_evaluation_language(payload, target_language=target_language)
            return payload
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            continue
        except LanguageMismatchError as exc:
            raise EvaluationError(str(exc)) from exc
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            raise EvaluationError("Gemini timeout while evaluating interview") from exc
        except httpx.HTTPStatusError as exc:
            raise EvaluationError(f"Gemini HTTP error: {exc.response.status_code}") from exc
        except Exception as exc:
            raise EvaluationError(f"Failed to evaluate interview: {str(exc)}") from exc

    raise EvaluationError(f"Gemini returned invalid evaluation JSON after retries: {last_error}")
