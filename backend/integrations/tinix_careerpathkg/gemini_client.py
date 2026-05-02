from __future__ import annotations

from typing import Any

import httpx

from core.config import get_settings


def _build_endpoint(api_key: str | None, model: str | None = None) -> str:
    settings = get_settings()
    effective_key = api_key or settings.gemini_api_key
    effective_model = model or settings.gemini_model
    if not effective_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{effective_model}:generateContent?key={effective_key}"
    )


def call_gemini_text(*, system_prompt: str, user_prompt: str, api_key: str | None = None, model: str | None = None, timeout_seconds: int = 60) -> str:
    endpoint = _build_endpoint(api_key, model)
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "text/plain",
        },
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(endpoint, json=payload)
        response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned empty content")
    return text


def call_gemini_json(*, system_prompt: str, user_prompt: str, api_key: str | None = None, model: str | None = None, timeout_seconds: int = 60) -> dict[str, Any]:
    raw = call_gemini_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
    )
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Gemini response does not contain JSON")
    import json

    return json.loads(raw[start : end + 1])
