import asyncio
import logging
import tempfile
from pathlib import Path
import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)


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


def _build_warmup_pdf_bytes() -> bytes:
    # Minimal valid PDF with one page and a tiny text stream.
    objects: list[bytes] = []
    offsets: list[int] = []

    def add_object(body: bytes) -> None:
        offsets.append(sum(len(obj) for obj in objects) + len(b"%PDF-1.4\n"))
        objects.append(body)

    add_object(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    add_object(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    add_object(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
    )
    add_object(b"4 0 obj << /Length 44 >> stream BT /F1 24 Tf 72 120 Td (warmup) Tj ET endstream endobj\n")
    add_object(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    body = b"%PDF-1.4\n" + b"".join(objects)
    xref_start = len(body)
    xref = [b"xref\n0 6\n0000000000 65535 f \n"]
    for offset in offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))

    trailer = (
        b"trailer << /Size 6 /Root 1 0 R >>\n"
        b"startxref\n"
        + str(xref_start).encode("ascii")
        + b"\n%%EOF\n"
    )
    return body + b"".join(xref) + trailer


async def parse_resume_to_markdown(file_bytes: bytes, filename: str) -> str:
    """Parse a CV (PDF or DOCX) to Markdown.

    * For normal‑size CVs (≤ 10 MB) we first try the **Quick Parse API** (MinerU Agent API).
    * If `MINERU_DISABLED` is set, we **never** fall back to the local MinerU CLI – an error is raised for files that exceed Quick Parse limits.
    * When the flag is off, the previous fallback behaviour (local MinerU) is kept.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise ResumeParseError("Unsupported file type")

    settings = get_settings()

    # -----------------------------------------------------------------
    # Try Quick Parse (Agent API) first for files ≤ 10 MB
    # -----------------------------------------------------------------
    QUICK_MAX_BYTES = 10 * 1024 * 1024
    if len(file_bytes) <= QUICK_MAX_BYTES:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # Step 1: Request signed upload URL
                resp = await client.post(
                    "https://mineru.net/api/v1/agent/parse/file",
                    json={"file_name": filename}
                )
                resp.raise_for_status()
                json_resp = resp.json()
                if json_resp.get("code") != 0 or "data" not in json_resp:
                    raise ResumeParseError(f"Quick Parse init failed: {json_resp.get('msg')}")

                data = json_resp["data"]
                task_id = data["task_id"]
                file_url = data["file_url"]

                # Step 2: Upload file bytes (PUT) without headers (Aliyun OSS requirement)
                upload_resp = await client.put(file_url, content=file_bytes)
                upload_resp.raise_for_status()

                # Step 3: Poll for completion
                markdown_url = None
                poll_timeout = settings.mineru_timeout_seconds
                poll_interval = 2.0
                deadline = asyncio.get_running_loop().time() + poll_timeout

                while asyncio.get_running_loop().time() < deadline:
                    poll_resp = await client.get(f"https://mineru.net/api/v1/agent/parse/{task_id}")
                    poll_resp.raise_for_status()
                    poll_data = poll_resp.json()

                    if poll_data.get("code") == 0:
                        task_data = poll_data.get("data", {})
                        state = task_data.get("state")
                        if state == "done":
                            markdown_url = task_data.get("markdown_url")
                            break
                        elif state == "failed":
                            err_msg = task_data.get("err_msg", "unknown error")
                            raise ResumeParseError(f"Quick Parse backend failed: {err_msg}")
                    await asyncio.sleep(poll_interval)

                if not markdown_url:
                    raise ResumeParseError("Quick Parse timed out on MinerU server")

                # Step 4: Download markdown content
                md_resp = await client.get(markdown_url)
                md_resp.raise_for_status()
                return md_resp.text

        except Exception as exc:
            # If MinerU is disabled, we cannot fallback to CLI, so raise error
            if getattr(settings, "mineru_disabled", False):
                raise ResumeParseError(f"Quick Parse failed and local MinerU is disabled: {exc}") from exc
            # Otherwise, log the warning and fall back to local CLI below
            logger.warning(f"Quick Parse failed, falling back to local MinerU CLI: {exc}")

    # If the file is > 10MB or Quick Parse failed, we fall back to local CLI
    if getattr(settings, "mineru_disabled", False):
        raise ResumeParseError("File exceeds Quick-Parse size limit (10 MB) and local MinerU is disabled.")

    # ---------- Fallback to local MinerU CLI ----------
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
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(), timeout=settings.mineru_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ResumeParseError(
                f"MinerU parsing timed out after {settings.mineru_timeout_seconds} seconds"
            ) from exc

        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="ignore").strip()
            if "No such file or directory" in error_text or "not recognized" in error_text:
                raise ResumeParseError("MinerU CLI is not installed or not in PATH")
            raise ResumeParseError(f"MinerU parsing failed: {error_text or 'unknown error'}")

        return _find_best_markdown(output_path)


async def warmup_mineru() -> None:
    settings = get_settings()
    if not settings.mineru_backend:
        return

    warmup_pdf = _build_warmup_pdf_bytes()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        input_path = tmp_dir_path / "warmup.pdf"
        output_path = tmp_dir_path / "mineru_warmup_output"
        output_path.mkdir(parents=True, exist_ok=True)
        input_path.write_bytes(warmup_pdf)

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
        try:
            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.mineru_warmup_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ResumeParseError(
                f"MinerU warmup timed out after {settings.mineru_warmup_timeout_seconds} seconds"
            ) from exc

        if process.returncode != 0:
            error_text = stderr.decode("utf-8", errors="ignore").strip()
            raise ResumeParseError(f"MinerU warmup failed: {error_text or 'unknown error'}")
