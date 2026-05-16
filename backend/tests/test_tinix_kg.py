from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from integrations.tinix_careerpathkg.kg_store import TinixCareerKGStore, build_artifact, normalize_label, write_artifact
from services import career_kg
from services.evaluation_kg import build_evaluation_kg_context


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class TinixKGStoreTests(unittest.TestCase):
    def test_normalize_and_deduplicate_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp)
            _write_jsonl(
                data_dir / "req_skill_matching.jsonl",
                [
                    {"req": "Thành thạo Python", "skill": "Python", "label": 1},
                    {"req": "thanh thao python", "skill": "python", "label": 1},
                    {"req": "Thành thạo Python", "skill": "Excel", "label": 0},
                ],
            )
            _write_jsonl(
                data_dir / "req_sum.jsonl",
                [{"input_text": "thanh thao python", "target_text": "Python backend"}],
            )

            artifact = build_artifact(data_dir)

        self.assertEqual(normalize_label("Thành thạo Python"), "thanh thao python")
        self.assertEqual(artifact["counts"]["pairs"], 2)
        pair = artifact["pair_labels"]["thanh thao python||python"]
        self.assertEqual(pair["label"], 1)
        self.assertEqual(pair["count"], 2)

    def test_cv_jd_matching_uses_tinix_labels_and_prioritizes_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "source"
            data_dir.mkdir()
            _write_jsonl(
                data_dir / "req_skill_matching.jsonl",
                [
                    {"req": "Build REST APIs with Python", "skill": "Python FastAPI", "label": 1},
                    {"req": "Build REST APIs with Python", "skill": "Excel reporting", "label": 0},
                    {"req": "Deploy services with Docker", "skill": "Docker", "label": 1},
                ],
            )
            _write_jsonl(data_dir / "req_sum.jsonl", [])
            artifact_dir = Path(temp) / "artifact"
            write_artifact(data_dir, artifact_dir)
            store = TinixCareerKGStore.load(artifact_dir)

            payload = career_kg._build_graph_enrichment(
                store=store,
                job_title="Backend Engineer",
                job_description="- Build REST APIs with Python\n- Deploy services with Docker",
                experience_level="junior",
                candidate_skills=["Python FastAPI"],
                version_suffix="test",
            )

        api_match = next(match for match in payload.skill_matches if "REST APIs" in match.requirement)
        docker_gap = next(gap for gap in payload.skill_gaps if "Docker" in gap.skill)
        self.assertEqual(api_match.relation, "exact")
        self.assertGreaterEqual(api_match.score, 0.85)
        self.assertEqual(docker_gap.severity, "critical")
        self.assertEqual(payload.question_targets[0].requirement, docker_gap.skill)
        self.assertGreater(payload.question_targets[0].priority, 0.5)

    def test_evaluation_context_includes_expected_evidence(self) -> None:
        question_doc = {
            "source": "job_only",
            "job_title": "Backend Engineer",
            "experience_level": "junior",
            "questions": [
                {
                    "question": "How have you deployed services with Docker?",
                    "target_skill": "Docker",
                    "why_asked": "Verify deployment evidence",
                    "kg_requirement": "Deploy services with Docker",
                    "kg_gap_severity": "critical",
                    "kg_priority": 0.91,
                }
            ],
            "kg_enrichment": {
                "enabled": True,
                "source": "Tinix-CareerPathKG",
                "version": "tinix-kg-json-v1:test",
                "confidence": 0.5,
                "skill_gaps": [
                    {
                        "skill": "Deploy services with Docker",
                        "severity": "critical",
                        "recommendation": "Prepare Docker deployment evidence",
                    }
                ],
                "skill_matches": [],
                "question_targets": [
                    {
                        "requirement": "Deploy services with Docker",
                        "skill": "Docker",
                        "priority": 0.91,
                        "difficulty": "hard",
                        "why_asked": "Verify deployment evidence",
                        "gap_severity": "critical",
                        "evidence": ["Tinix positive pair: Deploy services with Docker -> Docker"],
                    }
                ],
                "career_guidance": {"recommendations": ["Prepare Docker evidence"]},
            },
        }

        context, kg = build_evaluation_kg_context(question_doc)

        self.assertIsNotNone(kg)
        self.assertIn("requirement_to_verify=Deploy services with Docker", context or "")
        self.assertIn("expected_evidence=Tinix positive pair", context or "")
        self.assertIn("priority=0.91", context or "")


if __name__ == "__main__":
    unittest.main()
