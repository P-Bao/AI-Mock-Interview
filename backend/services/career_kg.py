from __future__ import annotations

import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from core.config import get_settings
from integrations.tinix_careerpathkg import TinixCareerKGStore
from integrations.tinix_careerpathkg import (
    CareerGraph,
    classify_requirement_skill_pairs,
    compute_skill_gap,
    generate_career_guidance,
    summarize_requirements,
)
from models.career_kg import CareerGuidance, KGEnrichmentPayload, QuestionTarget, RequirementCluster, SkillGap, SkillMatch

_TINIX_STORE: TinixCareerKGStore | None = None
_TINIX_STORE_ERROR: str | None = None


def _resolve_artifact_dir(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (Path(__file__).resolve().parents[1] / path).resolve()


def _get_tinix_store() -> TinixCareerKGStore | None:
    global _TINIX_STORE, _TINIX_STORE_ERROR
    if _TINIX_STORE is not None:
        return _TINIX_STORE
    if _TINIX_STORE_ERROR is not None:
        return None

    settings = get_settings()
    try:
        _TINIX_STORE = TinixCareerKGStore.load(_resolve_artifact_dir(settings.kg_artifact_dir))
        return _TINIX_STORE
    except Exception as exc:
        _TINIX_STORE_ERROR = str(exc)
        return None


_STOP_WORDS = {
    "the",
    "and",
    "or",
    "for",
    "with",
    "to",
    "of",
    "a",
    "an",
    "in",
    "on",
    "at",
    "by",
    "is",
    "are",
    "be",
    "as",
    "from",
    "that",
    "this",
    "you",
    "we",
    "will",
    "should",
}

_CATEGORY_KEYWORDS = {
    "Tools & Platforms": {
        "python",
        "java",
        "javascript",
        "typescript",
        "sql",
        "excel",
        "power bi",
        "tableau",
        "docker",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "git",
        "linux",
        "fastapi",
        "django",
        "flask",
        "react",
        "node",
        "api",
    },
    "Experience & Domain": {
        "experience",
        "years",
        "background",
        "production",
        "portfolio",
        "project",
        "domain",
        "industry",
        "ownership",
        "delivery",
        "analysis",
        "reporting",
    },
    "Soft Skills": {
        "communication",
        "team",
        "collaboration",
        "leadership",
        "problem solving",
        "critical thinking",
        "presentation",
        "stakeholder",
        "adaptability",
        "learning",
    },
}


def _normalize_text(value: str) -> str:
    text = re.sub(r"[^a-z0-9\s+/#.-]", " ", value.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(value: str) -> set[str]:
    tokens = set()
    for token in re.split(r"[\s+/,#.-]+", _normalize_text(value)):
        if token and token not in _STOP_WORDS:
            tokens.add(token)
    return tokens


def _split_requirements(job_description: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in job_description.splitlines():
        line = raw_line.strip().lstrip("-*•\u2022").strip()
        if len(line) >= 4:
            candidates.append(line)

    if not candidates:
        candidates = [part.strip() for part in re.split(r"(?<=[.!?])\s+", job_description) if len(part.strip()) >= 4]

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = _normalize_text(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(item)
    return cleaned[:16]


def _cluster_name(requirement: str) -> str:
    normalized = _normalize_text(requirement)
    for cluster_name, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return cluster_name
    return "Core Requirements"


def _score_text_pair(requirement: str, candidate_skill: str) -> float:
    req_norm = _normalize_text(requirement)
    skill_norm = _normalize_text(candidate_skill)
    if not req_norm or not skill_norm:
        return 0.0
    if req_norm == skill_norm:
        return 1.0
    if req_norm in skill_norm or skill_norm in req_norm:
        return 0.92

    req_tokens = _tokenize(requirement)
    skill_tokens = _tokenize(candidate_skill)
    if not req_tokens or not skill_tokens:
        return SequenceMatcher(None, req_norm, skill_norm).ratio()

    token_overlap = len(req_tokens & skill_tokens) / max(len(req_tokens), len(skill_tokens))
    sequence_ratio = SequenceMatcher(None, req_norm, skill_norm).ratio()
    return max(token_overlap, sequence_ratio)


def _best_match(requirement: str, candidate_skills: list[str]) -> tuple[str, float]:
    best_skill = ""
    best_score = 0.0
    for skill in candidate_skills:
        score = _score_text_pair(requirement, skill)
        if score > best_score:
            best_skill = skill
            best_score = score
    return best_skill, best_score


def _extract_candidate_skills(analysis: Any) -> list[str]:
    pool: list[str] = []
    skills_match = getattr(analysis, "skills_match", None)
    if skills_match is not None:
        pool.extend(getattr(skills_match, "matched", []) or [])
        pool.extend(getattr(skills_match, "missing_required", []) or [])
        pool.extend(getattr(skills_match, "missing_preferred", []) or [])

    pool.extend(getattr(analysis, "recommended_interview_focus", []) or [])
    pool.extend([item.area for item in getattr(analysis, "strengths", []) or [] if getattr(item, "area", None)])
    pool.extend([item.area for item in getattr(analysis, "gaps", []) or [] if getattr(item, "area", None)])

    deduped: list[str] = []
    seen: set[str] = set()
    for item in pool:
        normalized = _normalize_text(str(item))
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(str(item))
    return deduped


def _build_clusters_from_requirements(requirements: list[str]) -> list[dict[str, Any]]:
    cluster_map: dict[str, list[str]] = {}
    for requirement in requirements:
        cluster_name = _cluster_name(requirement)
        cluster_map.setdefault(cluster_name, []).append(requirement)

    total_requirements = len(requirements)
    clusters: list[dict[str, Any]] = []
    for name, items in cluster_map.items():
        skill_weight = round(1 / max(len(items), 1), 4)
        clusters.append(
            {
                "cluster": name,
                "weight": round(len(items) / max(total_requirements, 1), 4),
                "skills": [{"name": item, "weight": skill_weight} for item in items],
            }
        )
    return clusters


def _gap_priority(severity: str, match_score: float, cluster_weight: float = 1.0) -> float:
    severity_weight = {"critical": 1.0, "moderate": 0.68, "minor": 0.38}.get(severity, 0.5)
    missing_weight = max(0.0, 1.0 - match_score)
    return round(min(1.0, (severity_weight * 0.7 + missing_weight * 0.3) * max(cluster_weight, 0.3)), 4)


def _difficulty_for_priority(priority: float) -> str:
    if priority >= 0.75:
        return "hard"
    if priority >= 0.45:
        return "medium"
    return "easy"


def _build_question_targets(
    *,
    skill_gaps: list[SkillGap],
    skill_matches: list[SkillMatch],
    limit: int = 12,
) -> list[QuestionTarget]:
    targets: list[QuestionTarget] = []
    matched_by_requirement = {_normalize_text(match.requirement): match for match in skill_matches}

    for gap in sorted(skill_gaps, key=lambda item: item.priority, reverse=True):
        match = matched_by_requirement.get(_normalize_text(gap.skill))
        evidence = list(gap.evidence)
        if match is not None:
            evidence.extend(match.evidence[:2])
        why_asked = (
            f"Verify {gap.severity} requirement gap and collect concrete project evidence."
            if gap.severity == "critical"
            else "Check whether the candidate can provide enough evidence for this requirement."
        )
        targets.append(
            QuestionTarget(
                requirement=gap.skill,
                skill=match.cv_skill if match and match.cv_skill else gap.skill,
                priority=gap.priority,
                difficulty=_difficulty_for_priority(gap.priority),
                why_asked=why_asked,
                gap_severity=gap.severity,
                evidence=evidence[:4],
            )
        )

    for match in skill_matches:
        if len(targets) >= limit:
            break
        if match.relation not in {"exact", "related"}:
            continue
        priority = round(max(0.2, min(0.7, 1.0 - match.score + 0.2)), 4)
        targets.append(
            QuestionTarget(
                requirement=match.requirement,
                skill=match.cv_skill or match.requirement,
                priority=priority,
                difficulty=_difficulty_for_priority(priority),
                why_asked="Validate the strongest claimed skill against the job requirement.",
                gap_severity=None,
                evidence=match.evidence[:4],
            )
        )

    deduped: list[QuestionTarget] = []
    seen: set[str] = set()
    for target in sorted(targets, key=lambda item: item.priority, reverse=True):
        key = _normalize_text(target.requirement)
        if key and key not in seen:
            seen.add(key)
            deduped.append(target)
    return deduped[:limit]


def _build_skill_gaps(requirements: list[str], candidate_skills: list[str]) -> list[SkillGap]:
    gaps: list[SkillGap] = []
    for requirement in requirements:
        best_skill, best_score = _best_match(requirement, candidate_skills)
        if best_score >= 0.6:
            continue

        normalized = _normalize_text(requirement)
        if any(keyword in normalized for keyword in _CATEGORY_KEYWORDS["Experience & Domain"]):
            severity = "critical" if best_score < 0.3 else "moderate"
        elif any(keyword in normalized for keyword in _CATEGORY_KEYWORDS["Tools & Platforms"]):
            severity = "moderate" if best_score < 0.3 else "minor"
        else:
            severity = "moderate" if best_score < 0.35 else "minor"

        recommendation = f"Build evidence for: {requirement}"
        if best_skill:
            recommendation = f"Close the gap between '{best_skill}' and '{requirement}' with project evidence or guided practice."

        gaps.append(
            SkillGap(
                skill=requirement,
                severity=severity,
                reason="The requirement is not strongly evidenced in the current CV analysis.",
                recommendation=recommendation,
                priority=_gap_priority(severity, best_score),
            )
        )
    return gaps


def _build_empty_payload(*, reason: str) -> KGEnrichmentPayload:
    return KGEnrichmentPayload(enabled=False, version="disabled", error=reason)


def _build_graph_enrichment(
    *,
    store: TinixCareerKGStore,
    job_title: str,
    job_description: str,
    experience_level: str,
    candidate_skills: list[str],
    version_suffix: str,
) -> KGEnrichmentPayload:
    started_at = time.perf_counter()
    requirements = _split_requirements(job_description) or [job_title]

    cluster_map: dict[str, dict[str, Any]] = {}
    matches: list[SkillMatch] = []
    gaps: list[SkillGap] = []

    for requirement in requirements:
        lookup = store.lookup_requirement(requirement)
        cluster_name = lookup.cluster if lookup else _cluster_name(requirement)
        cluster = cluster_map.setdefault(cluster_name, {"requirements": [], "evidence": [], "source": store.source})
        cluster["requirements"].append(requirement)
        if lookup is not None:
            cluster["evidence"].extend(lookup.examples[:2])

        best_skill = ""
        best_score = 0.0
        evidence: list[str] = lookup.examples[:2] if lookup is not None else []
        if candidate_skills:
            best_skill, best_score, evidence, lookup = store.best_skill_match(
                requirement,
                candidate_skills,
                fallback_score=_score_text_pair,
            )

        if best_score >= 0.85:
            relation = "exact"
        elif best_score >= 0.5:
            relation = "related"
        elif best_skill:
            relation = "unknown"
        else:
            relation = "missing"

        matches.append(
            SkillMatch(
                requirement=requirement,
                cv_skill=best_skill,
                score=round(best_score, 4),
                relation=relation,
                evidence_source=store.source,
                evidence=evidence[:4],
            )
        )

        if relation not in {"exact", "related"}:
            normalized = _normalize_text(requirement)
            if lookup is not None and lookup.positive_skills:
                severity = "critical" if best_score < 0.35 else "moderate"
            elif any(keyword in normalized for keyword in _CATEGORY_KEYWORDS["Experience & Domain"]):
                severity = "critical" if best_score < 0.3 else "moderate"
            else:
                severity = "moderate" if best_score < 0.35 else "minor"

            recommendation = f"Prepare project evidence for: {requirement}"
            if lookup is not None and lookup.positive_skills:
                recommendation = f"Prepare evidence using related Tinix skills: {', '.join(lookup.positive_skills[:3])}"
            elif best_skill:
                recommendation = f"Bridge '{best_skill}' to '{requirement}' with concrete implementation evidence."

            gaps.append(
                SkillGap(
                    skill=requirement,
                    severity=severity,
                    reason="Tinix KG did not find strong CV evidence for this job requirement.",
                    recommendation=recommendation,
                    priority=_gap_priority(severity, best_score),
                    evidence_source=store.source,
                    evidence=evidence[:4],
                )
            )

    total = max(len(requirements), 1)
    clusters = [
        RequirementCluster(
            name=name,
            weight=round(len(data["requirements"]) / total, 4),
            requirements=data["requirements"],
            evidence_source=data["source"],
            evidence=list(dict.fromkeys(data["evidence"]))[:5],
        )
        for name, data in cluster_map.items()
    ]
    confidence = round(len([item for item in matches if item.relation in {"exact", "related"}]) / total, 4)
    question_targets = _build_question_targets(skill_gaps=gaps, skill_matches=matches)
    guidance = CareerGuidance(
        target_role=job_title,
        path=[f"{experience_level} -> {job_title}"],
        path_probability=confidence,
        recommendations=[target.why_asked for target in question_targets[:5]]
        or [f"Prepare evidence for the core requirements of {job_title}."],
    )
    processing_time_ms = int((time.perf_counter() - started_at) * 1000)

    return KGEnrichmentPayload(
        enabled=True,
        source="Tinix-CareerPathKG",
        version=f"{store.version}:{version_suffix}",
        requirement_clusters=clusters,
        skill_matches=matches,
        skill_gaps=gaps,
        question_targets=question_targets,
        career_guidance=guidance,
        confidence=confidence,
        processing_time_ms=processing_time_ms,
        error=None,
    )


def build_job_kg_enrichment(
    *,
    job_title: str,
    job_description: str,
    experience_level: str,
) -> KGEnrichmentPayload:
    settings = get_settings()
    if not settings.kg_enabled or settings.kg_mode == "disabled":
        return _build_empty_payload(reason="kg_disabled")

    store = _get_tinix_store()
    if store is not None and settings.kg_mode in {"auto", "graph"}:
        return _build_graph_enrichment(
            store=store,
            job_title=job_title,
            job_description=job_description,
            experience_level=experience_level,
            candidate_skills=[],
            version_suffix="job-only",
        )

    started_at = time.perf_counter()
    requirements = _split_requirements(job_description) or [job_title]
    clusters = _build_clusters_from_requirements(requirements)
    skill_gaps = _build_skill_gaps(requirements, [])
    guidance = CareerGuidance(
        target_role=job_title,
        path=[f"{experience_level} -> {job_title}"],
        path_probability=0.0,
        recommendations=[gap.recommendation for gap in skill_gaps[:5]]
        or [f"Prepare evidence for the core requirements of {job_title}."],
    )
    processing_time_ms = int((time.perf_counter() - started_at) * 1000)

    return KGEnrichmentPayload(
        enabled=True,
        source="Tinix-CareerPathKG",
        version="job-only-heuristic",
        requirement_clusters=[
            RequirementCluster(
                name=cluster["cluster"],
                weight=cluster["weight"],
                requirements=[skill["name"] for skill in cluster["skills"]],
            )
            for cluster in clusters
        ],
        skill_matches=[
            SkillMatch(requirement=requirement, cv_skill="", score=0.0, relation="missing")
            for requirement in requirements
        ],
        skill_gaps=skill_gaps,
        question_targets=_build_question_targets(
            skill_gaps=skill_gaps,
            skill_matches=[
                SkillMatch(requirement=requirement, cv_skill="", score=0.0, relation="missing")
                for requirement in requirements
            ],
        ),
        career_guidance=guidance,
        confidence=0.0,
        processing_time_ms=processing_time_ms,
        error=None,
    )


def _build_vendor_enrichment(
    *,
    analysis: Any,
    cv_markdown: str,
    job_title: str,
    job_description: str,
    experience_level: str,
) -> KGEnrichmentPayload:
    settings = get_settings()
    requirements = _split_requirements(job_description) or [job_title]
    candidate_skills = _extract_candidate_skills(analysis) or [job_title, experience_level]
    clusters = _build_clusters_from_requirements(requirements)
    cluster_models: list[RequirementCluster] = []

    for cluster in clusters:
        try:
            cluster_name = summarize_requirements([skill["name"] for skill in cluster["skills"]], api_key=settings.gemini_api_key)
        except Exception:
            cluster_name = cluster["cluster"]
        cluster_models.append(
            RequirementCluster(
                name=(cluster_name or cluster["cluster"]).strip(),
                weight=cluster["weight"],
                requirements=[skill["name"] for skill in cluster["skills"]],
            )
        )

    pairs = []
    pair_records: list[tuple[str, str, float]] = []
    for requirement in requirements:
        best_skill, best_score = _best_match(requirement, candidate_skills)
        pair_records.append((requirement, best_skill or "", best_score))
        pairs.append((requirement, best_skill or candidate_skills[0]))

    labels: list[int] = []
    for batch_start in range(0, len(pairs), 5):
        batch = pairs[batch_start : batch_start + 5]
        parsed = classify_requirement_skill_pairs(batch, api_key=settings.gemini_api_key)
        for i in range(len(batch)):
            labels.append(int(parsed.get(f"pair_{i+1}", 0) or 0))

    matches: list[SkillMatch] = []
    gap_names: list[str] = []
    for idx, requirement in enumerate(requirements):
        best_skill, best_score = pair_records[idx][1], pair_records[idx][2]
        matched = labels[idx] if idx < len(labels) else 0
        if matched:
            relation = "exact" if best_score >= 0.8 else "related"
        else:
            relation = "unknown" if best_skill else "missing"

        matches.append(
            SkillMatch(
                requirement=requirement,
                cv_skill=best_skill,
                score=round(best_score, 4),
                relation=relation,
            )
        )
        if not matched or best_score < 0.6:
            gap_names.append(requirement)

    if not gap_names:
        gap_names = [req for req in requirements if req not in {item.requirement for item in matches if item.relation in {"exact", "related"}}]

    skill_gaps = _build_skill_gaps(gap_names or requirements, candidate_skills)
    confidence = round(len([item for item in matches if item.relation in {"exact", "related"}]) / max(len(matches), 1), 4)

    guidance_text = ""
    try:
        guidance_text = generate_career_guidance([gap.skill for gap in skill_gaps], [("Candidate", experience_level), (job_title, experience_level)], api_key=settings.gemini_api_key)
    except Exception:
        guidance_text = "; ".join(gap.recommendation for gap in skill_gaps[:3])

    guidance = CareerGuidance(
        target_role=job_title,
        path=[f"{experience_level} -> {job_title}"],
        path_probability=confidence,
        recommendations=[guidance_text] if guidance_text else [],
    )

    return KGEnrichmentPayload(
        enabled=True,
        source="Tinix-CareerPathKG",
        version="gemini",
        requirement_clusters=cluster_models,
        skill_matches=matches,
        skill_gaps=skill_gaps,
        question_targets=_build_question_targets(skill_gaps=skill_gaps, skill_matches=matches),
        career_guidance=guidance,
        confidence=confidence,
        processing_time_ms=0,
        error=None,
    )


def _build_heuristic_enrichment(
    *,
    analysis: Any,
    cv_markdown: str,
    job_title: str,
    job_description: str,
    experience_level: str,
) -> KGEnrichmentPayload:
    started_at = time.perf_counter()
    requirements = _split_requirements(job_description) or [job_title]
    candidate_skills = _extract_candidate_skills(analysis) or ([job_title, experience_level] if cv_markdown.strip() else [job_title])
    clusters = _build_clusters_from_requirements(requirements)

    matches: list[SkillMatch] = []
    for requirement in requirements:
        best_skill, best_score = _best_match(requirement, candidate_skills)
        if best_score >= 0.8:
            relation = "exact"
        elif best_score >= 0.45:
            relation = "related"
        elif best_skill:
            relation = "unknown"
        else:
            relation = "missing"

        matches.append(
            SkillMatch(
                requirement=requirement,
                cv_skill=best_skill or "",
                score=round(best_score, 4),
                relation=relation,
            )
        )

    skill_gaps = _build_skill_gaps(requirements, candidate_skills)
    confidence = round(len([item for item in matches if item.score >= 0.45]) / max(len(requirements), 1), 4)
    guidance = CareerGuidance(
        target_role=job_title,
        path=[f"Strengthen {gap.skill}" for gap in skill_gaps[:3]] or [f"Maintain and document current strengths for {job_title}"],
        path_probability=confidence,
        recommendations=[gap.recommendation for gap in skill_gaps[:5]] or [f"Prepare targeted interview evidence for the {job_title} role."],
    )
    processing_time_ms = int((time.perf_counter() - started_at) * 1000)

    return KGEnrichmentPayload(
        enabled=True,
        source="Tinix-CareerPathKG",
        version="heuristic",
        requirement_clusters=[
            RequirementCluster(
                name=cluster["cluster"],
                weight=cluster["weight"],
                requirements=[skill["name"] for skill in cluster["skills"]],
            )
            for cluster in clusters
        ],
        skill_matches=matches,
        skill_gaps=skill_gaps,
        question_targets=_build_question_targets(skill_gaps=skill_gaps, skill_matches=matches),
        career_guidance=guidance,
        confidence=confidence,
        processing_time_ms=processing_time_ms,
        error=None,
    )


async def build_career_kg_enrichment(
    *,
    analysis: Any,
    cv_markdown: str,
    job_title: str,
    job_description: str,
    experience_level: str,
) -> KGEnrichmentPayload:
    settings = get_settings()
    if not settings.kg_enabled or settings.kg_mode == "disabled":
        return _build_empty_payload(reason="kg_disabled")

    candidate_skills = _extract_candidate_skills(analysis) or ([job_title, experience_level] if cv_markdown.strip() else [job_title])
    store = _get_tinix_store()
    if store is not None and settings.kg_mode in {"auto", "graph"}:
        try:
            return _build_graph_enrichment(
                store=store,
                job_title=job_title,
                job_description=job_description,
                experience_level=experience_level,
                candidate_skills=candidate_skills,
                version_suffix="cv-jd",
            )
        except Exception:
            if settings.kg_mode == "graph":
                return _build_heuristic_enrichment(
                    analysis=analysis,
                    cv_markdown=cv_markdown,
                    job_title=job_title,
                    job_description=job_description,
                    experience_level=experience_level,
                )

    if settings.kg_mode in {"auto", "model"} and settings.gemini_api_key:
        try:
            return _build_vendor_enrichment(
                analysis=analysis,
                cv_markdown=cv_markdown,
                job_title=job_title,
                job_description=job_description,
                experience_level=experience_level,
            )
        except Exception as exc:
            if settings.kg_mode == "model":
                return KGEnrichmentPayload(
                    enabled=False,
                    source="Tinix-CareerPathKG",
                    version="gemini",
                    processing_time_ms=0,
                    error=f"tinix_vendor_unavailable: {exc}",
                )
    elif settings.kg_mode == "model" and not settings.gemini_api_key:
        return _build_empty_payload(reason="gemini_api_key_missing")

    return _build_heuristic_enrichment(
        analysis=analysis,
        cv_markdown=cv_markdown,
        job_title=job_title,
        job_description=job_description,
        experience_level=experience_level,
    )


def enrich_questions_with_kg_metadata(
    questions: list[dict[str, Any]],
    kg_enrichment: KGEnrichmentPayload | None,
) -> list[dict[str, Any]]:
    if kg_enrichment is None or not kg_enrichment.enabled:
        return questions

    gap_lookup = {_normalize_text(item.skill): item for item in kg_enrichment.skill_gaps}
    match_lookup = {_normalize_text(item.requirement): item for item in kg_enrichment.skill_matches}
    target_lookup = {_normalize_text(item.skill): item for item in kg_enrichment.question_targets}
    target_lookup.update({_normalize_text(item.requirement): item for item in kg_enrichment.question_targets})

    enriched: list[dict[str, Any]] = []
    for question in questions:
        question_copy = dict(question)
        target_skill = question_copy.get("target_skill", "")
        normalized_target = _normalize_text(str(target_skill))
        kg_requirement = None
        kg_match_score = None
        kg_gap_severity = None
        kg_priority = None

        if normalized_target in gap_lookup:
            gap = gap_lookup[normalized_target]
            kg_requirement = gap.skill
            kg_gap_severity = gap.severity
            kg_match_score = 0.0
            kg_priority = gap.priority
        else:
            best_match = None
            best_score = 0.0
            for match in kg_enrichment.skill_matches:
                score = max(
                    _score_text_pair(target_skill, match.requirement),
                    _score_text_pair(target_skill, match.cv_skill),
                )
                if score > best_score:
                    best_match = match
                    best_score = score
            if best_match is not None and best_score > 0:
                kg_requirement = best_match.requirement
                kg_match_score = round(best_score, 4)

        if kg_requirement is None and normalized_target in match_lookup:
            match = match_lookup[normalized_target]
            kg_requirement = match.requirement
            kg_match_score = match.score

        target = target_lookup.get(normalized_target)
        if target is not None:
            kg_requirement = kg_requirement or target.requirement
            kg_gap_severity = kg_gap_severity or target.gap_severity
            kg_priority = target.priority

        question_copy["kg_requirement"] = kg_requirement
        question_copy["kg_match_score"] = kg_match_score
        question_copy["kg_gap_severity"] = kg_gap_severity
        question_copy["kg_priority"] = kg_priority
        enriched.append(question_copy)

    return enriched
