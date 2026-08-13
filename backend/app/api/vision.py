"""CV API: POST /api/v1/image-quality-check.

Cheap, no-AI check. Accepts a JSON body { "image": "data:image/...;base64,..." }
or a multipart file. Requires login. Returns a validated VisionResult.
"""
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..auth.deps import require_user
from ..schemas.vision import VisionResult
from ._imageio import bytes_from_upload, check_size, from_data_url

router = APIRouter(prefix="/api/v1", tags=["vision"])


@router.post("/image-quality-check", response_model=VisionResult)
async def image_quality_check(
    request: Request,
    file: UploadFile | None = File(default=None),
    user=Depends(require_user),
):
    if file is not None:
        data = await bytes_from_upload(file)
    else:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Send an image file or JSON { image }.")
        data = check_size(from_data_url(body.get("image", "")))

    from vision.pipeline import analyze
    try:
        return analyze(data)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Could not process this image.")
