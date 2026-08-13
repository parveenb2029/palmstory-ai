"""CV pipeline: bytes → preprocess → quality → detect → structured result."""
import time
import uuid

from .palm_detection.detect import detect
from .preprocessing.preprocess import load_and_normalize
from .quality.quality import assess


def analyze(data: bytes) -> dict:
    t0 = time.time()
    img = load_and_normalize(data)
    quality = assess(img)
    detection = detect(img)
    return {
        "request_id": uuid.uuid4().hex[:12],
        "normalized_size": list(img.size),
        "quality": quality,
        "detection": detection,
        "processing_ms": int((time.time() - t0) * 1000),
    }
