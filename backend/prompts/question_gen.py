QUESTION_GEN_SYSTEM_PROMPT_TEMPLATE = """You are an experienced technical interviewer.
Generate exactly {num_questions} interview questions tailored to this specific candidate.
Mix question types: technical (verify claimed skills), behavioral (past experience),
situational (how they'd handle scenarios relevant to the role).
Base difficulty on experience_level: junior=mostly easy/medium, mid=medium/hard, senior=hard+system design.
If KG context is provided, prioritize questions that probe the highest skill gaps and weakest evidence.
Return ONLY valid JSON - no markdown, no explanation.

Schema:
{{
  "questions": [
    {{
      "question": str,
      "type": "technical|behavioral|situational",
      "difficulty": "easy|medium|hard",
      "target_skill": str,
      "why_asked": str
    }}
  ]
}}
"""



def build_question_gen_user_prompt(
    *,
    job_title: str,
    experience_level: str,
    strengths_summary: str,
    gaps_summary: str,
    recommended_focus: str,
    matched_skills: str,
    missing_required: str,
    kg_context: str = "",
) -> str:
    return f"""Job Title: {job_title}
Experience Level: {experience_level}

Candidate strengths: {strengths_summary}
Candidate gaps: {gaps_summary}
Recommended focus areas: {recommended_focus}
Matched skills: {matched_skills}
Missing required skills: {missing_required}
KG context: {kg_context}
"""
