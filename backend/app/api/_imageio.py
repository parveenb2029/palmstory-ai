"""Shared, safe extraction of image bytes from requests (data URL or upload)."""
import base64
import re

from fastapi import HTTPException, UploadFile

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
_DATAURL_RE = re.compile(r"^data:(?P<type>image/[\w.+-]+);base64,(?P<b64>.+)$", re.DOTALL)


def from_data_url(url: str) -> bytes:
    if not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Expected a base64 image data URL.")
    m = _DATAURL_RE.match(url)
    if not m:
        raise HTTPException(status_code=400, detail="Expected a base64 image data URL.")
    if m.group("type") not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type.")
    try:
        return base64.b64decode(m.group("b64"), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed image data.")


def check_size(data: bytes) -> bytes:
    if not data:
        raise HTTPException(status_code=400, detail="No image provided.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large (max 10 MB).")
    return data


async def bytes_from_upload(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported image type.")
    return check_size(await file.read())
