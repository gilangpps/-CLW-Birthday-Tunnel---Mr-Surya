"""Input validation and sanitization for public visitor submissions."""

import html
import re
from pathlib import Path

from config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIMES,
    MAX_IMAGE_BYTES,
    MAX_MESSAGE_LENGTH,
    MAX_NAME_LENGTH,
)

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MULTI_SPACE = re.compile(r"\s+")


def sanitize_text(value: str, max_length: int) -> str:
    """Strip control characters and collapse whitespace before storage."""
    if not value:
        return ""

    text = html.unescape(value).strip()
    text = CONTROL_CHARS.sub("", text)
    text = MULTI_SPACE.sub(" ", text)
    return text[:max_length]


def validate_name(value: str) -> tuple[bool, str, str]:
    cleaned = sanitize_text(value, MAX_NAME_LENGTH)
    if not cleaned:
        return False, "", "Nama pengirim wajib diisi."
    return True, cleaned, ""


def validate_message(value: str) -> tuple[bool, str, str]:
    cleaned = sanitize_text(value, MAX_MESSAGE_LENGTH)
    if not cleaned:
        return False, "", "Pesan ucapan wajib diisi."
    return True, cleaned, ""


def validate_image(
    filename: str | None,
    content_type: str | None,
    data: bytes | None,
) -> tuple[bool, str, str]:
    if not data:
        return False, "", "Foto wajib diunggah atau diambil dari kamera."

    if len(data) > MAX_IMAGE_BYTES:
        return False, "", "Ukuran foto terlalu besar. Maksimal 8 MB."

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime and mime not in ALLOWED_IMAGE_MIMES:
        return False, "", "Format foto tidak didukung. Gunakan JPG, PNG, atau WebP."

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = ".jpg"

    if data[:3] == b"\xff\xd8\xff":
        return True, ".jpg", ""

    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True, ".png", ""

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True, ".webp", ""

    return False, "", "File bukan gambar yang valid."
