"""Response schemas for the CV endpoints (validated output — spec §39)."""
from typing import Optional

from pydantic import BaseModel


class QualityReport(BaseModel):
    brightness: float
    sharpness: float
    resolution: str
    coverage: float
    score: float
    usable: bool
    reasons: list[str]


class Detection(BaseModel):
    detected: bool
    source: str                       # mediapipe | heuristic | unavailable
    hand_side: Optional[str] = None
    landmarks: int = 0
    orientation_ok: Optional[bool] = None
    skin_ratio: Optional[float] = None
    note: str = ""


class VisionResult(BaseModel):
    request_id: str
    normalized_size: list[int]
    quality: QualityReport
    detection: Detection
    processing_ms: int
