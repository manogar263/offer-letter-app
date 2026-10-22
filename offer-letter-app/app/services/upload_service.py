import uuid
from pathlib import Path

from fastapi import UploadFile

from ..config import ALLOWED_IMAGE_EXT, MAX_UPLOAD_BYTES, UPLOAD_DIR


class UploadError(ValueError):
    pass


async def save_image(file: UploadFile | None, prefix: str) -> str | None:
    """Validate and store an uploaded image. Returns the stored filename or None."""
    if file is None or not file.filename:
        return None

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise UploadError(
            f"{prefix.title()} must be one of: {', '.join(sorted(ALLOWED_IMAGE_EXT))}"
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(f"{prefix.title()} is larger than 2 MB")
    if not data:
        raise UploadError(f"{prefix.title()} file is empty")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}-{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return name
