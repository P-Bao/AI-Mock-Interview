import asyncio
import json
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from core.config import get_settings
from models.evaluation import EvaluationPayload
from prompts.evaluation import EVALUATION_SYSTEM_PROMPT


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

    def _sync_call() -> str:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=[types.Content(role="user", parts=[types.Part(text=json.dumps(payload))])],
            config=types.GenerateContentConfig(
                system_instruction=EVALUATION_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
                top_p=0.8,
                max_output_tokens=4096,
            ),
        )
        return response.text or ""

    return await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout_seconds)


async def evaluate_interview(*, transcript: list[dict[str, str]], timeout_seconds: int = 90) -> EvaluationPayload:
    settings = get_settings()
    retries = max(settings.eval_max_retries, 1)

    base_payload: dict[str, Any] = {"interview": transcript}
    repair_instruction = (
        "Return only valid JSON matching schema. "
        "No markdown, no explanation, and ensure numeric ranges are respected."
    )
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            payload = (
                base_payload
                if attempt == 0
                else {"interview": transcript, "repair_instruction": repair_instruction}
            )
            raw = await _call_gemini(payload, timeout_seconds=timeout_seconds)
            if not raw.strip():
                raise EvaluationError("Gemini returned empty content")
            data = _extract_json(raw)
            return EvaluationPayload.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            continue
        except asyncio.TimeoutError as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            raise EvaluationError("Gemini timeout while evaluating interview") from exc
        except Exception as exc:
            raise EvaluationError(f"Failed to evaluate interview: {str(exc)}") from exc

    raise EvaluationError(f"Gemini returned invalid evaluation JSON after retries: {last_error}")
