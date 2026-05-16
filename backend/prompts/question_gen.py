QUESTION_GEN_SYSTEM_PROMPT_TEMPLATE = """You are an experienced technical interviewer.
Generate exactly {num_questions} interview questions tailored to this specific candidate.
Mix question types: technical (verify claimed skills), behavioral (past experience),
situational (how they'd handle scenarios relevant to the role).
Base difficulty on experience_level: intern/fresher=mostly easy (fundamentals), junior=easy/medium, mid=medium/hard (independence), senior=hard+system design, lead=hard+system design+leadership/mentorship.
If KG context is provided, prioritize questions that probe the highest skill gaps and weakest evidence.
Write every natural-language string in the JSON response in the target language provided by the user prompt.
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
    job_description: str = "",
    experience_level: str,
    strengths_summary: str,
    gaps_summary: str,
    recommended_focus: str,
    matched_skills: str,
    missing_required: str,
    kg_context: str = "",
    target_language: str = "en",
) -> str:
    return f"""Job Title: {job_title}
Experience Level: {experience_level}
Job Description: {job_description or "not provided"}
Target Language: {target_language}

Candidate strengths: {strengths_summary}
Candidate gaps: {gaps_summary}
Recommended focus areas: {recommended_focus}
Matched skills: {matched_skills}
Missing required skills: {missing_required}
KG context: {kg_context}
"""
