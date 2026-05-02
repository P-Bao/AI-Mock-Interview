from __future__ import annotations

from .gemini_client import call_gemini_text


SYSTEM_PROMPT = """
You are an expert in analyzing IT-related skills.
Your task is to compare a job requirement from a job description (jd_requirement) with a skill extracted from a resume (cv_skill), and classify their relationship into one of the following four labels:

0 – Disjoint:
The two items belong to different domains, share no meaningful overlap, and cannot substitute for each other in IT work.

1 – Related: Includes the following cases:
- Partial semantic overlap: the two items share some common ground (same domain, same purpose, or used in similar types of work) but neither fully contains the other.
- jd_requirement is a broad concept or domain, and cv_skill is a narrower subfield, subtype, or specific variant within it. Condition: everyone who has cv_skill is assumed to satisfy jd_requirement, but not vice versa.
- cv_skill is a broad concept or domain, and jd_requirement is a narrower subfield, subtype, or specific variant within it. Condition: everyone who satisfies jd_requirement is assumed to have cv_skill, but not vice versa.

Input: a list of 5 requirement-skill pairs:
- Pair 1: jd_requirement = "{jd_req_1}", cv_skill = "{cv_skill_1}"
- Pair 2: jd_requirement = "{jd_req_2}", cv_skill = "{cv_skill_2}"
- Pair 3: jd_requirement = "{jd_req_3}", cv_skill = "{cv_skill_3}"
- Pair 4: jd_requirement = "{jd_req_4}", cv_skill = "{cv_skill_4}"
- Pair 5: jd_requirement = "{jd_req_5}", cv_skill = "{cv_skill_5}"

Output requirement: return the result in JSON format:
{
  "pair_1": 0 or 1,
  "pair_2": 0 or 1,
  "pair_3": 0 or 1,
  "pair_4": 0 or 1,
  "pair_5": 0 or 1
}
"""


def classify_requirement_skill_pairs(pairs: list[tuple[str, str]], api_key: str | None = None) -> dict[str, int]:
    padded = list(pairs[:5])
    while len(padded) < 5:
        padded.append(("", ""))

    prompt = SYSTEM_PROMPT.format(
        jd_req_1=padded[0][0], cv_skill_1=padded[0][1],
        jd_req_2=padded[1][0], cv_skill_2=padded[1][1],
        jd_req_3=padded[2][0], cv_skill_3=padded[2][1],
        jd_req_4=padded[3][0], cv_skill_4=padded[3][1],
        jd_req_5=padded[4][0], cv_skill_5=padded[4][1],
    )
    raw = call_gemini_text(system_prompt=SYSTEM_PROMPT, user_prompt=prompt, api_key=api_key)

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    import json

    parsed = json.loads(raw[start : end + 1])
    return {key: int(value) for key, value in parsed.items() if key.startswith("pair_")}
