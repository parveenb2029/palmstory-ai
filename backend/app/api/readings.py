"""Readings API — async job pipeline (Phase 11).

POST /api/v1/readings
    Runs the cheap quality gate synchronously. If the image is unusable, returns
    the reasons immediately (no job, no AI). Otherwise creates a background job
    and returns 202 with a job_id.

GET /api/v1/readings/{job_id}
    Poll job status/stage/progress; includes the full result when complete.
    Owner-only (404 for anyone else, so job existence isn't leaked).
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.deps import require_user
from ..db import get_db
from ..jobs.runner import submit
from ..models.job import Job
from ..schemas.vision import Detection, QualityReport
from ..security import reading_rate_limiter
from ._imageio import bytes_from_upload, check_size, from_data_url

router = APIRouter(prefix="/api/v1", tags=["readings"])


class JobAccepted(BaseModel):
    job_id: Optional[str]
    status: str                       # queued | rejected
    quality: QualityReport
    detection: Detection


class JobStatus(BaseModel):
    job_id: str
    status: str                       # queued | processing | complete | failed
    stage: str
    progress: int
    error: Optional[str] = None
    reading_id: Optional[str] = None
    result: Optional[dict] = None


def _norm_hand(value: str) -> str:
    return "left" if str(value or "right").strip().lower().startswith("l") else "right"


@router.post("/readings")
async def create_reading(
    request: Request,
    file: UploadFile | None = File(default=None),
    hand: str = Form(default="right"),
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    if not reading_rate_limiter.allow(user.id):
        raise HTTPException(status_code=429, detail="Too many readings this hour — please try again later.")

    if file is not None:
        data = await bytes_from_upload(file)
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Send an image file or JSON { image, hand }.")
        hand = body.get("hand", hand)
        data = check_size(from_data_url(body.get("image", "")))
    hand = _norm_hand(hand)

    from vision.preprocessing.preprocess import load_and_normalize, to_jpeg_bytes
    from vision.quality.quality import assess
    from vision.palm_detection.detect import detect
    from PIL import Image as _PILImage

    try:
        img = load_and_normalize(data)
    except _PILImage.DecompressionBombError:
        raise HTTPException(status_code=422, detail="Image is too large to process safely.")
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this image.")

    quality = assess(img)
    detection = detect(img)

    # cheap gate: reject bad images immediately — no job, no AI spent
    if not quality["usable"]:
        return JSONResponse(status_code=200, content=JobAccepted(
            job_id=None, status="rejected", quality=quality, detection=detection).model_dump())

    job = Job(user_id=user.id, hand=hand, status="queued", stage="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    submit(job.id, to_jpeg_bytes(img), hand, quality, detection, list(img.size))

    return JSONResponse(status_code=202, content=JobAccepted(
        job_id=job.id, status="queued", quality=quality, detection=detection).model_dump())


@router.get("/readings/{job_id}", response_model=JobStatus)
def get_reading(job_id: str, user=Depends(require_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Reading not found.")
    result = json.loads(job.result_json) if job.result_json else None
    reading_id = result.get("reading_id") if result else None
    return JobStatus(job_id=job.id, status=job.status, stage=job.stage,
                     progress=job.progress, error=job.error,
                     reading_id=reading_id, result=result)
