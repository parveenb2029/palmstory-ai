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
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user, owner_key
from ..db import get_db
from ..jobs.runner import submit
from ..models.job import Job
from ..models.user import User
from ..schemas.vision import Detection, QualityReport
from ..security import reading_rate_limiter
from ._imageio import bytes_from_upload, check_size, from_data_url

router = APIRouter(prefix="/api/v1", tags=["readings"])

FREE_GUEST_READINGS = int(os.getenv("GUEST_FREE_READINGS", "1"))  # free readings before sign-up; raise for testing


class JobAccepted(BaseModel):
    job_id: Optional[str]
    status: str                       # queued | rejected | marginal
    quality: QualityReport
    detection: Detection
    can_override: bool = False        # true when a borderline shot may be used anyway


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
    allow_marginal: bool = Form(default=False),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_guest = user is None

    # guests get one free reading per browser; more requires an account
    if is_guest and request.session.get("guest_readings", 0) >= FREE_GUEST_READINGS:
        return JSONResponse(status_code=200, content={
            "status": "signup_required",
            "detail": "Sign up (free) to get more readings and to ask questions about your reading."})

    owner = owner_key(request, user)
    if not reading_rate_limiter.allow(owner):
        raise HTTPException(status_code=429, detail="Too many readings this hour — please try again later.")

    if file is not None:
        data = await bytes_from_upload(file)
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Send an image file or JSON { image, hand }.")
        hand = body.get("hand", hand)
        allow_marginal = bool(body.get("allow_marginal", allow_marginal))
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

    # Quality gate. Severe problems (no palm, too small, near-black/white) are
    # blocking. Borderline problems (a bit soft or dim) can be used anyway, so a
    # reasonable shot is never trapped — "conditions apply" rather than a hard no.
    if not quality["usable"]:
        blocking = quality.get("blocking", True)
        if blocking or not allow_marginal:
            return JSONResponse(status_code=200, content=JobAccepted(
                job_id=None,
                status="rejected" if blocking else "marginal",
                quality=quality, detection=detection,
                can_override=not blocking).model_dump())
        # else: borderline + user chose to proceed → fall through

    job = Job(user_id=owner, hand=hand, status="queued", stage="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    # persist to history only for logged-in users; guests get the reading but no saved history
    submit(job.id, to_jpeg_bytes(img), hand, quality, detection, list(img.size),
           persist_reading=not is_guest)

    if is_guest:
        request.session["guest_readings"] = request.session.get("guest_readings", 0) + 1

    return JSONResponse(status_code=202, content=JobAccepted(
        job_id=job.id, status="queued", quality=quality, detection=detection).model_dump())


@router.get("/readings/{job_id}", response_model=JobStatus)
def get_reading(job_id: str, request: Request,
                user: Optional[User] = Depends(get_current_user),
                db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    owner = user.id if user else request.session.get("guest_id")
    if job is None or job.user_id != owner:
        raise HTTPException(status_code=404, detail="Reading not found.")
    result = json.loads(job.result_json) if job.result_json else None
    reading_id = result.get("reading_id") if result else None
    return JobStatus(job_id=job.id, status=job.status, stage=job.stage,
                     progress=job.progress, error=job.error,
                     reading_id=reading_id, result=result)
