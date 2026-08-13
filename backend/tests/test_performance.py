"""Phase 15: compression, static caching, pipeline speed budget (mock)."""
import os
import tempfile
import time

import numpy as np
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "perf.db")

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.services.pipeline import generate_reading  # noqa: E402
from vision.preprocessing.preprocess import to_jpeg_bytes  # noqa: E402


def test_static_assets_are_cacheable():
    r = TestClient(app).get("/static/css/app.css")
    assert r.status_code == 200
    assert "max-age" in r.headers.get("cache-control", "")


def test_large_responses_are_gzipped():
    # landing page is comfortably over the gzip threshold
    r = TestClient(app).get("/", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_pipeline_is_fast_on_mocks():
    q = {"brightness": 140, "sharpness": 200, "resolution": "640x480",
         "coverage": 0.5, "score": 90, "usable": True, "reasons": []}
    d = {"detected": True, "source": "heuristic", "note": ""}
    rng = np.random.default_rng(0)
    jpeg = to_jpeg_bytes(Image.fromarray(rng.integers(90, 190, size=(480, 640, 3), dtype=np.uint8), "RGB"))
    generate_reading(jpeg, "right", q, d, [640, 480])  # warm up
    t0 = time.perf_counter()
    generate_reading(jpeg, "right", q, d, [640, 480])
    assert (time.perf_counter() - t0) < 0.5  # generous budget; mock is ~1ms
