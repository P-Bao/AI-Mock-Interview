from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from models.evaluation import EvaluationPayload, OverallEvaluation, QuestionEvaluation, STARScores

SupportedLanguage = Literal["en", "vi"]


class LanguageMismatchError(Exception):
    def __init__(self, *, field: str, target_language: SupportedLanguage, detected_language: str) -> None:
        self.field = field
        self.target_language = target_language
        self.detected_language = detected_language
        super().__init__(
            f"language_mismatch: {field} must be {target_language}, detected {detected_language}"
        )


@dataclass(frozen=True)
class LanguageCheck:
    field: str
    target_language: SupportedLanguage
    detected_language: str
    is_mismatch: bool


_VIETNAMESE_DIACRITIC_RE = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ"
    r"ùúụủũưừứựửữỳýỵỷỹđ"
    r"ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠ"
    r"ÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ]"
)
_WORD_RE = re.compile(r"[a-zA-ZÀ-ỹ]+")

_EN_STOPWORDS = {
    "a",
    "about",
    "and",
    "are",
    "as",
    "at",
    "be",
    "build",
    "can",
    "data",
    "design",
    "for",
    "from",
    "have",
    "how",
    "i",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "what",
    "when",
    "with",
    "you",
}

_VI_STOPWORDS = {
    "anh",
    "ban",
    "bang",
    "cac",
    "cach",
    "can",
    "cau",
    "cho",
    "cong",
    "cua",
    "da",
    "de",
    "du",
    "duoc",
    "em",
    "gia",
    "hay",
    "hoc",
    "khong",
    "ky",
    "la",
    "lam",
    "mot",
    "nao",
    "nguoi",
    "phan",
    "qua",
    "ra",
    "sinh",
    "su",
    "tai",
    "the",
    "toi",
    "trong",
    "tu",
    "va",
    "ve",
    "viec",
    "voi",
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").replace("đ", "d").replace("Đ", "D")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(text)]


def detect_language(text: str) -> SupportedLanguage | Literal["unknown"]:
    tokens = _tokens(text)
    if not tokens:
        return "unknown"

    plain_tokens = [_strip_accents(token).lower() for token in tokens]
    vi_diacritics = len(_VIETNAMESE_DIACRITIC_RE.findall(text))
    vi_score = sum(1 for token in plain_tokens if token in _VI_STOPWORDS)
    en_score = sum(1 for token in plain_tokens if token in _EN_STOPWORDS)

    if vi_diacritics >= 2:
        return "vi"
    if vi_diacritics == 1 and vi_score >= 1:
        return "vi"
    if vi_score >= 3 and vi_score >= en_score:
        return "vi"
    if en_score >= 3 and en_score > vi_score:
        return "en"
    if en_score >= 2 and len(tokens) <= 8 and en_score > vi_score:
        return "en"
    return "unknown"


def detect_target_language(job_description: str) -> SupportedLanguage:
    detected = detect_language(job_description)
    return detected if detected in {"en", "vi"} else "en"


def check_language(text: str, *, target_language: SupportedLanguage, field: str) -> LanguageCheck:
    detected = detect_language(text)
    return LanguageCheck(
        field=field,
        target_language=target_language,
        detected_language=detected,
        is_mismatch=detected in {"en", "vi"} and detected != target_language,
    )


def validate_text_language(text: str, *, target_language: SupportedLanguage, field: str) -> None:
    check = check_language(text, target_language=target_language, field=field)
    if check.is_mismatch:
        raise LanguageMismatchError(
            field=field,
            target_language=target_language,
            detected_language=check.detected_language,
        )


def validate_questions_language(questions: list[dict], *, target_language: SupportedLanguage) -> None:
    text_parts: list[str] = []
    for question in questions:
        text_parts.extend(
            [
                str(question.get("question") or ""),
                str(question.get("why_asked") or ""),
            ]
        )
    validate_text_language("\n".join(text_parts), target_language=target_language, field="questions")


def find_transcript_language_mismatch(
    transcript: list[dict[str, str]], *, target_language: SupportedLanguage
) -> LanguageCheck | None:
    for index, entry in enumerate(transcript):
        role = entry.get("role", "unknown")
        check = check_language(
            entry.get("text") or "",
            target_language=target_language,
            field=f"interview[{index}].{role}",
        )
        if check.is_mismatch:
            return check
    return None


def validate_evaluation_language(payload: EvaluationPayload, *, target_language: SupportedLanguage) -> None:
    text = "\n".join(
        [
            *(question.comment for question in payload.questions),
            *payload.overall.strengths,
            *payload.overall.key_improvements,
            payload.overall.overall_comment,
        ]
    )
    validate_text_language(text, target_language=target_language, field="evaluation")


def build_language_mismatch_evaluation(
    transcript: list[dict[str, str]],
    *,
    target_language: SupportedLanguage,
    mismatch: LanguageCheck,
) -> EvaluationPayload:
    message = (
        f"Language mismatch: expected {target_language}, but {mismatch.field} was detected as "
        f"{mismatch.detected_language}. The interview fails because all questions and answers must use the "
        "job description language."
    )
    if target_language == "vi":
        message = (
            f"Bất đồng ngôn ngữ: yêu cầu dùng {target_language}, nhưng {mismatch.field} được phát hiện là "
            f"{mismatch.detected_language}. Buổi phỏng vấn bị đánh trượt vì toàn bộ câu hỏi và câu trả lời "
            "phải cùng ngôn ngữ với mô tả công việc."
        )

    questions: list[QuestionEvaluation] = []
    current_question = ""
    question_index = 0
    for entry in transcript:
        if entry.get("role") == "model":
            current_question = entry.get("text") or ""
            continue
        if entry.get("role") != "user":
            continue
        question_index += 1
        questions.append(
            QuestionEvaluation(
                question_index=question_index,
                question_text=current_question,
                answer_text=entry.get("text") or "",
                star_scores=STARScores(situation=0, task=0, action=0, result=0),
                question_score=0.0,
                comment=message,
            )
        )

    if not questions:
        questions.append(
            QuestionEvaluation(
                question_index=1,
                question_text="",
                answer_text="",
                star_scores=STARScores(situation=0, task=0, action=0, result=0),
                question_score=0.0,
                comment=message,
            )
        )

    return EvaluationPayload(
        questions=questions,
        overall=OverallEvaluation(
            overall_score=0.0,
            strengths=[],
            key_improvements=[message],
            overall_comment=message,
        ),
    )
