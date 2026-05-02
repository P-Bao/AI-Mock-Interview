from __future__ import annotations

from .gemini_client import call_gemini_text


SYSTEM_PROMPT = """
You are an expert in text analysis. Your task is to read a list of skill-related sentences belonging to the same cluster and summarize them into a single representative sentence, following these requirements:

- Produce an abstractive summary; do not copy any sentence verbatim.
- Select only one core skill that best represents the entire cluster.
- If there are synonymous expressions, keep only the most common phrasing.
- For software tools, always normalize the format to "using [tool]".
- Do not use parentheses, do not add explanations, and do not provide comments.
- Output must be a single concise line.

List of skills:
{skill_list}

Output format: one single concise summary line only.
"""


def summarize_requirements(requirements: list[str], api_key: str | None = None) -> str:
    prompt = SYSTEM_PROMPT.format(skill_list="\n".join(f'"{item}",' for item in requirements))
    return call_gemini_text(system_prompt=SYSTEM_PROMPT, user_prompt=prompt, api_key=api_key)
