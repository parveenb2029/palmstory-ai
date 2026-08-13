"""Job runner.

Default: an in-process thread pool — works with just `uvicorn`, no broker.
Set JOBS_SYNC=true to run jobs inline (handy for tests / simple deployments).
For horizontal scaling, swap this for Redis + RQ (see docs/architecture.md);
the API and job model don't change.

The image bytes are passed in memory to the worker and never written to disk,
preserving the privacy model.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor

from ..db import SessionLocal
from ..models.job import Job
from ..providers.base import ProviderError
from ..services.pipeline import generate_reading

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="reading-job")


def _sync() -> bool:
    return os.getenv("JOBS_SYNC", "false").strip().lower() in ("1", "true", "yes", "on")


def submit(job_id: str, image_bytes: bytes, hand: str,
           quality: dict, detection: dict, normalized_size: list,
           persist_reading: bool = True) -> None:
    args = (job_id, image_bytes, hand, quality, detection, normalized_size, persist_reading)
    if _sync():
        _run(*args)
    else:
        _executor.submit(_run, *args)


def _run(job_id, image_bytes, hand, quality, detection, normalized_size, persist_reading=True):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "processing"
        job.stage = "analyzing"
        db.commit()

        def on_stage(name, pct):
            job.stage = name
            job.progress = pct
            db.commit()

        result = generate_reading(image_bytes, hand, quality, detection,
                                  normalized_size, on_stage=on_stage)

        # promote to a durable, owner-scoped Reading — only for logged-in users
        if persist_reading:
            from ..services.reading_store import create as create_reading
            reading = create_reading(db, job.user_id, hand, result)
            result["reading_id"] = reading.id
            reading.data_json = json.dumps(result)   # include reading_id in stored copy

        job.result_json = json.dumps(result)
        job.status = "complete"
        job.stage = "done"
        job.progress = 100
        db.commit()
    except ProviderError as e:
        _fail(db, job_id, f"A model was unavailable: {e}")
    except Exception as e:  # never let a worker crash silently
        _fail(db, job_id, f"Unexpected error: {e}")
    finally:
        db.close()


def _fail(db, job_id, message):
    job = db.get(Job, job_id)
    if job:
        job.status = "failed"
        job.stage = "failed"
        job.error = message[:500]
        db.commit()
