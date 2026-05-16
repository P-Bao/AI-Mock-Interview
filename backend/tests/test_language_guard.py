import unittest

from services.language_guard import (
    LanguageMismatchError,
    build_language_mismatch_evaluation,
    detect_language,
    detect_target_language,
    find_transcript_language_mismatch,
    validate_questions_language,
    validate_text_language,
)


class LanguageGuardTests(unittest.TestCase):
    def test_detects_english_and_vietnamese(self) -> None:
        self.assertEqual(
            detect_target_language(
                "Build AI software with Python, analyze data, and communicate results with the team."
            ),
            "en",
        )
        self.assertEqual(
            detect_language("Ứng viên cần phân tích dữ liệu và xây dựng mô hình học máy."),
            "vi",
        )

    def test_cv_language_mismatch_raises(self) -> None:
        with self.assertRaises(LanguageMismatchError) as ctx:
            validate_text_language(
                "Tôi đã xây dựng mô hình học máy cho đồ án tốt nghiệp và phân tích dữ liệu.",
                target_language="en",
                field="cv_markdown",
            )

        self.assertIn("language_mismatch", str(ctx.exception))

    def test_question_language_mismatch_raises(self) -> None:
        with self.assertRaises(LanguageMismatchError):
            validate_questions_language(
                [
                    {
                        "question": "Bạn đã triển khai mô hình AI như thế nào?",
                        "why_asked": "Kiểm tra khả năng triển khai và đánh giá mô hình.",
                    }
                ],
                target_language="en",
            )

    def test_english_questions_and_answers_pass_guard(self) -> None:
        transcript = [
            {"role": "model", "text": "Tell me about a machine learning project you built."},
            {
                "role": "user",
                "text": "I built a churn prediction model, cleaned the data, trained a baseline, and improved F1 score.",
            },
        ]

        self.assertIsNone(find_transcript_language_mismatch(transcript, target_language="en"))

    def test_transcript_mismatch_builds_fail_all_payload(self) -> None:
        transcript = [
            {"role": "model", "text": "Tell me about a machine learning project you built."},
            {"role": "user", "text": "Em đã làm một dự án phân loại ảnh và đánh giá kết quả."},
        ]

        mismatch = find_transcript_language_mismatch(transcript, target_language="en")
        self.assertIsNotNone(mismatch)
        payload = build_language_mismatch_evaluation(
            transcript,
            target_language="en",
            mismatch=mismatch,
        )

        self.assertEqual(payload.overall.overall_score, 0)
        self.assertEqual(payload.questions[0].question_score, 0)
        self.assertEqual(payload.questions[0].star_scores.situation, 0)
        self.assertIn("Language mismatch", payload.overall.overall_comment)


if __name__ == "__main__":
    unittest.main()
