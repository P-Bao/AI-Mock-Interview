from typing import Any

from db.mongodb import get_db
from db.repositories.question_repo import QuestionRepository
from services.language_guard import SupportedLanguage, detect_target_language


def _format_list(items: list[str], limit: int = 5) -> str:
    selected = [item for item in items if item][:limit]
    return "; ".join(selected) if selected else "none"


def build_evaluation_kg_context(question_doc: dict[str, Any] | None) -> tuple[str | None, dict[str, Any] | None]:
    if not question_doc:
        return None, None

    kg_enrichment = question_doc.get("kg_enrichment")
    if not isinstance(kg_enrichment, dict) or not kg_enrichment.get("enabled"):
        return None, kg_enrichment if isinstance(kg_enrichment, dict) else None

    skill_gaps = kg_enrichment.get("skill_gaps") or []
    skill_matches = kg_enrichment.get("skill_matches") or []
    question_targets = kg_enrichment.get("question_targets") or []
    guidance = kg_enrichment.get("career_guidance") or {}
    questions = question_doc.get("questions") or []

    target_by_requirement = {
        str(item.get("requirement", "")).strip().lower(): item
        for item in question_targets
        if isinstance(item, dict)
    }
    match_by_requirement = {
        str(item.get("requirement", "")).strip().lower(): item
        for item in skill_matches
        if isinstance(item, dict)
    }

    gap_lines = []
    for gap in skill_gaps[:8]:
        if not isinstance(gap, dict):
            continue
        gap_lines.append(
            f"{gap.get('skill', '')} "
            f"(severity={gap.get('severity', 'unknown')}, recommendation={gap.get('recommendation', '')})"
        )

    match_lines = []
    for match in skill_matches[:8]:
        if not isinstance(match, dict):
            continue
        match_lines.append(
            f"{match.get('requirement', '')} -> {match.get('cv_skill', '')} "
            f"(score={match.get('score', 'n/a')}, relation={match.get('relation', 'unknown')})"
        )

    question_lines = []
    for idx, question in enumerate(questions[:12], start=1):
        if not isinstance(question, dict):
            continue
        question_lines.append(
            " | ".join(
                [
                    f"q{idx}: {question.get('question', '')}",
                    f"target_skill={question.get('target_skill', '')}",
                    f"kg_requirement={question.get('kg_requirement') or 'none'}",
                    f"kg_match_score={question.get('kg_match_score') if question.get('kg_match_score') is not None else 'n/a'}",
                    f"kg_gap_severity={question.get('kg_gap_severity') or 'none'}",
                    f"kg_priority={question.get('kg_priority') if question.get('kg_priority') is not None else 'n/a'}",
                    f"why_asked={question.get('why_asked', '')}",
                ]
            )
        )

    evaluation_lines = []
    for idx, question in enumerate(questions[:12], start=1):
        if not isinstance(question, dict):
            continue
        requirement = str(question.get("kg_requirement") or question.get("target_skill") or "")
        requirement_key = requirement.strip().lower()
        target = target_by_requirement.get(requirement_key) or {}
        match = match_by_requirement.get(requirement_key) or {}
        evidence = target.get("evidence") or match.get("evidence") or []
        related_skill = target.get("skill") or match.get("cv_skill") or question.get("target_skill", "")
        evaluation_lines.append(
            " | ".join(
                [
                    f"q{idx}",
                    f"requirement_to_verify={requirement or 'none'}",
                    f"related_skill={related_skill or 'none'}",
                    f"expected_evidence={_format_list([str(item) for item in evidence], limit=4)}",
                    f"gap_severity={question.get('kg_gap_severity') or target.get('gap_severity') or 'none'}",
                    f"priority={question.get('kg_priority') if question.get('kg_priority') is not None else target.get('priority', 'n/a')}",
                ]
            )
        )

    context = "\n".join(
        [
            f"Question source={question_doc.get('source', 'cv')}",
            f"KG source={kg_enrichment.get('source', 'unknown')}; version={kg_enrichment.get('version', 'unknown')}; confidence={kg_enrichment.get('confidence', 0)}",
            f"Job title={question_doc.get('job_title', '')}; experience_level={question_doc.get('experience_level', '')}",
            f"Top skill gaps: {_format_list(gap_lines, limit=8)}",
            f"Top skill matches: {_format_list(match_lines, limit=8)}",
            f"Career guidance: {_format_list(guidance.get('recommendations') or [], limit=3)}",
            f"Generated question KG metadata: {_format_list(question_lines, limit=12)}",
            f"Answer evaluation KG context: {_format_list(evaluation_lines, limit=12)}",
        ]
    )
    return context, kg_enrichment


async def load_evaluation_kg_context(question_session_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    if not question_session_id:
        return None, None

    db = await get_db()
    question_doc = await QuestionRepository(db).get_by_session_id(question_session_id)
    return build_evaluation_kg_context(question_doc)


async def load_evaluation_context_info(
    question_session_id: str | None,
) -> tuple[str | None, dict[str, Any] | None, SupportedLanguage | None]:
    if not question_session_id:
        return None, None, None

    db = await get_db()
    question_doc = await QuestionRepository(db).get_by_session_id(question_session_id)
    kg_context, kg_enrichment = build_evaluation_kg_context(question_doc)
    if not question_doc:
        return kg_context, kg_enrichment, None

    target_language = question_doc.get("target_language")
    if target_language in {"en", "vi"}:
        return kg_context, kg_enrichment, target_language

    job_description = question_doc.get("job_description") or ""
    return kg_context, kg_enrichment, detect_target_language(job_description) if job_description else None
