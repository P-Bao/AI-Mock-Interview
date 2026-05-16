from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ARTIFACT_FILENAME = "career_kg.json"
ARTIFACT_VERSION = "tinix-kg-json-v1"
EVIDENCE_SOURCE = "Tinix-CareerPathKG/data"

STOP_WORDS = {
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
    "co",
    "cua",
    "va",
    "voi",
    "cac",
    "la",
    "trong",
}

DOMAIN_KEYWORDS = {
    "frontend": {"react", "frontend", "css", "html", "javascript", "typescript", "vue", "angular"},
    "backend": {"api", "backend", "django", "flask", "fastapi", "java", "python", "node", "golang", "microservice"},
    "mobile": {"android", "ios", "mobile", "flutter", "react native"},
    "database": {"sql", "database", "postgres", "mysql", "mongodb", "redis", "warehouse"},
    "devops": {"devops", "docker", "kubernetes", "ci/cd", "aws", "gcp", "azure", "linux"},
    "ai_ml": {"ml", "ai", "machine learning", "deep learning", "llm", "data science", "pytorch", "tensorflow"},
    "blockchain": {"blockchain", "web3", "solidity", "smart contract", "ethereum", "defi"},
    "testing": {"test", "qa", "automation", "unit test", "selenium"},
    "soft_skills": {"communication", "team", "stakeholder", "collaboration", "leadership", "giao tiep", "lam viec nhom"},
}


@dataclass(frozen=True)
class RequirementLookup:
    text: str
    key: str
    domain: str
    cluster: str
    score: float
    positive_skills: list[str]
    negative_skills: list[str]
    examples: list[str]


def normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace("Đ", "d").lower()
    text = re.sub(r"[^a-z0-9\s+/#.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_label(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.split(r"[\s+/,#.-]+", normalize_label(value)):
        if token and token not in STOP_WORDS:
            tokens.add(token)
    return tokens


def text_similarity(left: str, right: str) -> float:
    left_norm = normalize_label(left)
    right_norm = normalize_label(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        return 0.92

    left_tokens = tokenize_label(left)
    right_tokens = tokenize_label(right)
    if not left_tokens or not right_tokens:
        return SequenceMatcher(None, left_norm, right_norm).ratio()

    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))
    sequence_ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    return max(overlap, sequence_ratio)


def infer_domain(*values: str) -> str:
    text = " ".join(normalize_label(value) for value in values)
    best_domain = "general"
    best_hits = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits:
            best_domain = domain
            best_hits = hits
    return best_domain


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _summary_cluster_lookup(summary_rows: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in summary_rows:
        target = str(row.get("target_text") or "").strip()
        input_text = str(row.get("input_text") or "")
        if not target:
            continue
        for line in input_text.splitlines():
            key = normalize_label(line)
            if key:
                lookup[key] = target
    return lookup


def build_artifact(data_dir: Path) -> dict[str, Any]:
    matching_rows = _read_jsonl(data_dir / "req_skill_matching.jsonl")
    summary_rows = _read_jsonl(data_dir / "req_sum.jsonl")
    cluster_lookup = _summary_cluster_lookup(summary_rows)

    pair_counts: dict[tuple[str, str], Counter[int]] = defaultdict(Counter)
    requirement_texts: dict[str, Counter[str]] = defaultdict(Counter)
    skill_texts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in matching_rows:
        requirement = str(row.get("requirement") or row.get("req") or "").strip()
        skill = str(row.get("skill") or row.get("matched_skill") or "").strip()
        if not requirement or not skill:
            continue
        label = 1 if int(row.get("label") or 0) == 1 else 0
        req_key = normalize_label(requirement)
        skill_key = normalize_label(skill)
        if not req_key or not skill_key:
            continue
        pair_counts[(req_key, skill_key)][label] += 1
        requirement_texts[req_key][requirement] += 1
        skill_texts[skill_key][skill] += 1

    req_positive: dict[str, Counter[str]] = defaultdict(Counter)
    req_negative: dict[str, Counter[str]] = defaultdict(Counter)
    edges: list[dict[str, Any]] = []
    pair_labels: dict[str, dict[str, Any]] = {}

    for (req_key, skill_key), counts in sorted(pair_counts.items()):
        label = 1 if counts[1] >= counts[0] else 0
        requirement = requirement_texts[req_key].most_common(1)[0][0]
        skill = skill_texts[skill_key].most_common(1)[0][0]
        confidence = max(counts.values()) / max(sum(counts.values()), 1)
        pair_key = f"{req_key}||{skill_key}"
        pair_labels[pair_key] = {
            "requirement": requirement,
            "skill": skill,
            "label": label,
            "confidence": round(confidence, 4),
            "count": sum(counts.values()),
        }
        relation = "MATCHES" if label else "NOT_MATCH"
        if label:
            req_positive[req_key][skill] += sum(counts.values())
        else:
            req_negative[req_key][skill] += sum(counts.values())
        edges.append(
            {
                "source": f"requirement:{req_key}",
                "target": f"skill:{skill_key}",
                "type": relation,
                "weight": round(confidence, 4),
            }
        )

    requirements: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    domain_nodes: set[str] = set()
    cluster_nodes: set[str] = set()
    for req_key, names in sorted(requirement_texts.items()):
        requirement = names.most_common(1)[0][0]
        cluster = cluster_lookup.get(req_key) or infer_domain(requirement).replace("_", " ").title()
        domain = infer_domain(requirement, cluster)
        positives = [skill for skill, _ in req_positive[req_key].most_common(12)]
        negatives = [skill for skill, _ in req_negative[req_key].most_common(8)]
        examples = [f"{requirement} -> {skill}" for skill in positives[:3]]
        requirements.append(
            {
                "id": f"requirement:{req_key}",
                "text": requirement,
                "key": req_key,
                "domain": domain,
                "cluster": cluster,
                "positive_skills": positives,
                "negative_skills": negatives,
                "examples": examples,
            }
        )
        nodes.append({"id": f"requirement:{req_key}", "type": "Requirement", "text": requirement})
        domain_nodes.add(domain)
        cluster_nodes.add(cluster)
        edges.append({"source": f"requirement:{req_key}", "target": f"domain:{domain}", "type": "BELONGS_TO_DOMAIN"})
        edges.append({"source": f"requirement:{req_key}", "target": f"cluster:{normalize_label(cluster)}", "type": "RELATED_TO"})

    skills: list[dict[str, Any]] = []
    for skill_key, names in sorted(skill_texts.items()):
        skill = names.most_common(1)[0][0]
        skills.append({"id": f"skill:{skill_key}", "text": skill, "key": skill_key})
        nodes.append({"id": f"skill:{skill_key}", "type": "Skill", "text": skill})

    for domain in sorted(domain_nodes):
        nodes.append({"id": f"domain:{domain}", "type": "Domain", "text": domain})
    for cluster in sorted(cluster_nodes):
        nodes.append({"id": f"cluster:{normalize_label(cluster)}", "type": "Cluster", "text": cluster})

    return {
        "version": ARTIFACT_VERSION,
        "source": EVIDENCE_SOURCE,
        "counts": {
            "requirements": len(requirements),
            "skills": len(skills),
            "pairs": len(pair_labels),
            "summary_clusters": len(cluster_lookup),
        },
        "nodes": nodes,
        "edges": edges,
        "requirements": requirements,
        "skills": skills,
        "pair_labels": pair_labels,
    }


def write_artifact(data_dir: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = build_artifact(data_dir)
    output_path = output_dir / ARTIFACT_FILENAME
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return output_path


class TinixCareerKGStore:
    def __init__(self, artifact: dict[str, Any]):
        self.artifact = artifact
        self.version = str(artifact.get("version") or ARTIFACT_VERSION)
        self.source = str(artifact.get("source") or EVIDENCE_SOURCE)
        self.requirements = list(artifact.get("requirements") or [])
        self.pair_labels = dict(artifact.get("pair_labels") or {})
        self._requirements_by_key = {item.get("key"): item for item in self.requirements if item.get("key")}

    @classmethod
    def load(cls, artifact_dir: Path) -> "TinixCareerKGStore":
        artifact_path = artifact_dir / ARTIFACT_FILENAME
        with artifact_path.open("r", encoding="utf-8") as handle:
            artifact = json.load(handle)
        if not isinstance(artifact, dict) or not artifact.get("requirements"):
            raise ValueError("Tinix KG artifact is empty or invalid")
        return cls(artifact)

    def lookup_requirement(self, requirement: str, *, min_score: float = 0.28) -> RequirementLookup | None:
        req_key = normalize_label(requirement)
        exact = self._requirements_by_key.get(req_key)
        if exact is not None:
            return self._to_lookup(exact, 1.0)

        best: dict[str, Any] | None = None
        best_score = 0.0
        for item in self.requirements:
            score = text_similarity(requirement, str(item.get("text") or ""))
            if score > best_score:
                best = item
                best_score = score
        if best is None or best_score < min_score:
            return None
        return self._to_lookup(best, best_score)

    def pair_label(self, requirement: str, skill: str) -> dict[str, Any] | None:
        return self.pair_labels.get(f"{normalize_label(requirement)}||{normalize_label(skill)}")

    def best_skill_match(
        self,
        requirement: str,
        candidate_skills: list[str],
        *,
        fallback_score,
    ) -> tuple[str, float, list[str], RequirementLookup | None]:
        lookup = self.lookup_requirement(requirement)
        best_skill = ""
        best_score = 0.0
        evidence: list[str] = []

        for skill in candidate_skills:
            label_record = self.pair_label(requirement, skill)
            direct_score = fallback_score(requirement, skill)
            score = direct_score
            skill_evidence: list[str] = []

            if label_record and label_record.get("label") == 1:
                score = max(score, 0.94 * float(label_record.get("confidence") or 1.0))
                skill_evidence.append(
                    f"Tinix positive pair: {label_record.get('requirement')} -> {label_record.get('skill')}"
                )
            elif label_record and label_record.get("label") == 0:
                score = min(score, 0.34)
                skill_evidence.append(
                    f"Tinix negative pair: {label_record.get('requirement')} -> {label_record.get('skill')}"
                )

            if lookup is not None:
                for positive_skill in lookup.positive_skills:
                    positive_score = fallback_score(skill, positive_skill)
                    if positive_score >= 0.8:
                        score = max(score, 0.88 * positive_score)
                        skill_evidence.append(f"Related Tinix skill for requirement: {positive_skill}")
                score = max(score, fallback_score(skill, lookup.text) * 0.8)

            if score > best_score:
                best_skill = skill
                best_score = score
                evidence = skill_evidence

        if lookup is not None and not evidence:
            evidence = lookup.examples[:2]
        return best_skill, min(best_score, 1.0), evidence, lookup

    def _to_lookup(self, item: dict[str, Any], score: float) -> RequirementLookup:
        return RequirementLookup(
            text=str(item.get("text") or ""),
            key=str(item.get("key") or ""),
            domain=str(item.get("domain") or "general"),
            cluster=str(item.get("cluster") or "Core Requirements"),
            score=score,
            positive_skills=[str(skill) for skill in item.get("positive_skills") or []],
            negative_skills=[str(skill) for skill in item.get("negative_skills") or []],
            examples=[str(example) for example in item.get("examples") or []],
        )
