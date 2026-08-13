"""Image preprocessing.

Decodes untrusted image bytes with Pillow, honours EXIF orientation, converts to
RGB, downsizes, and re-encodes to a clean JPEG. Re-encoding strips metadata and
neutralizes malformed/embedded content — the first line of upload safety.
"""
import io

from PIL import Image, ImageOps

# Decompression-bomb guard: reject absurd pixel counts before allocating them.
Image.MAX_IMAGE_PIXELS = 40_000_000  # ~40 MP; raises Image.DecompressionBombError beyond

MAX_DIM = 1280


def load_and_normalize(data: bytes, max_dim: int = MAX_DIM) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    w, h = img.size                     # from header — no pixels allocated yet
    if w * h > Image.MAX_IMAGE_PIXELS:  # hard reject before decoding (bomb guard)
        raise Image.DecompressionBombError(f"{w}x{h} exceeds the pixel limit")
    img.load()                          # force decode now (catches truncated files)
    img = ImageOps.exif_transpose(img)  # honour camera orientation
    img = img.convert("RGB")            # drop alpha / palette, normalize channels
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))
    return img


def to_jpeg_bytes(img: Image.Image, quality: int = 90) -> bytes:
    """Re-encode to a clean JPEG (no EXIF/metadata carried over)."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
