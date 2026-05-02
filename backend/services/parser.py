import asyncio
from pathlib import Path
import tempfile

from core.config import get_settings


class ResumeParseError(Exception):
    pass


def _find_best_markdown(output_dir: Path) -> str:
    markdown_files = list(output_dir.rglob("*.md"))
    if not markdown_files:
        raise ResumeParseError("MinerU output does not contain markdown files")

    best_text = ""
    for file_path in markdown_files:
        text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if len(text) > len(best_text):
            best_text = text

    if not best_text:
        raise ResumeParseError("MinerU produced empty markdown content")
    return best_text


async def parse_resume_to_markdown(file_bytes: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ResumeParseError("Unsupported file type")

    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / f"resume{suffix}"
        output_path = tmp_dir_path / "mineru_output"
        output_path.mkdir(parents=True, exist_ok=True)

        input_path.write_bytes(file_bytes)

        command = [
            "mineru",
            "-p",
            str(input_path),
            "-o",
            str(output_path),
            "-b",
            "vlm-auto-engine" if settings.mineru_backend == "vlm" else settings.mineru_backend,
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="ignore").strip()
            if "No such file or directory" in error_text or "not recognized" in error_text:
                raise ResumeParseError("MinerU CLI is not installed or not in PATH")
            raise ResumeParseError(f"MinerU parsing failed: {error_text or 'unknown error'}")

        return _find_best_markdown(output_path)
