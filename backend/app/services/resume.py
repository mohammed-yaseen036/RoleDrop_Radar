import os
import tempfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader


MAX_RESUME_BYTES = 5 * 1024 * 1024


def extract_text_from_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    if len(text) < 40:
        raise ValueError("The PDF does not contain enough extractable resume text.")
    return text


async def read_resume_pdf(upload: UploadFile) -> str:
    filename = (upload.filename or "").lower()
    if not filename.endswith(".pdf") or upload.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF resumes are accepted.",
        )
    content = await upload.read()
    if not content or len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume PDF must be non-empty and no larger than 5 MB.",
        )

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        try:
            return extract_text_from_pdf(temp_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unable to read resume text: {exc}",
            ) from exc
    finally:
        if temp_path and temp_path.exists():
            os.unlink(temp_path)

