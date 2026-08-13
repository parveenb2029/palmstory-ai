"""Phase 4 CV tests. Use synthetic images; no MediaPipe/network required."""
import base64
import io
import os
import re
import tempfile

import numpy as np
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "cv.db")
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402
from vision.quality.quality import assess  # noqa: E402
from vision.preprocessing.preprocess import load_and_normalize, to_jpeg_bytes  # noqa: E402
from vision.pipeline import analyze  # noqa: E402


def _img(kind="good", size=(640, 480)):
    w, h = size
    if kind == "dark":
        arr = np.full((h, w, 3), 10, dtype=np.uint8)
    elif kind == "blurry":
        arr = np.full((h, w, 3), 140, dtype=np.uint8)  # flat → low sharpness
    else:  # "good": textured, mid-bright
        rng = np.random.default_rng(0)
        arr = rng.integers(90, 190, size=(h, w, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


def _data_url(img):
    buf = io.BytesIO(); img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def test_quality_flags_dark_and_blur():
    good = assess(_img("good"))
    assert good["usable"] is True and good["score"] > 50
    dark = assess(_img("dark"))
    assert dark["usable"] is False and any("dark" in r.lower() for r in dark["reasons"])
    blur = assess(_img("blurry"))
    assert blur["usable"] is False


def test_preprocess_reencodes_and_downsizes():
    big = _img("good", size=(4000, 3000))
    buf = io.BytesIO(); big.save(buf, format="PNG")
    norm = load_and_normalize(buf.getvalue())
    assert max(norm.size) <= 1280 and norm.mode == "RGB"
    jpeg = to_jpeg_bytes(norm)
    assert jpeg[:2] == b"\xff\xd8"  # JPEG magic; metadata stripped


def test_pipeline_shape():
    buf = io.BytesIO(); _img("good").save(buf, format="JPEG")
    out = analyze(buf.getvalue())
    assert set(out) >= {"request_id", "normalized_size", "quality", "detection", "processing_ms"}
    assert out["detection"]["source"] in {"mediapipe", "heuristic"}


def test_endpoint_requires_auth():
    c = TestClient(app)
    r = c.post("/api/v1/image-quality-check", json={"image": "x"}, follow_redirects=False)
    assert r.status_code in (303, 307, 401, 403)


def test_endpoint_happy_path():
    c = TestClient(app)
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": "cv@ex.com", "password": "palmreader1", "csrf": tok})
    r = c.post("/api/v1/image-quality-check", json={"image": _data_url(_img("good"))})
    assert r.status_code == 200
    body = r.json()
    assert body["quality"]["usable"] is True
    assert "detection" in body and "request_id" in body


def test_endpoint_rejects_bad_data_url():
    c = TestClient(app)
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": "cv2@ex.com", "password": "palmreader1", "csrf": tok})
    r = c.post("/api/v1/image-quality-check", json={"image": "not-a-data-url"})
    assert r.status_code == 400
