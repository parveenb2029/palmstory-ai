"""Phase 11: async reading jobs — create, poll, ownership, gating."""
import base64
import io
import os
import re
import tempfile
import time

import numpy as np
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "jobs.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DEV_MOCK_AI"] = "true"
os.environ["JOBS_SYNC"] = "true"   # deterministic for most tests

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def _durl(kind="good"):
    if kind == "dark":
        arr = np.full((480, 640, 3), 10, dtype=np.uint8)
    else:
        rng = np.random.default_rng(0)
        arr = rng.integers(90, 190, size=(480, 640, 3), dtype=np.uint8)
    buf = io.BytesIO(); Image.fromarray(arr, "RGB").save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _client(email=None):
    c = TestClient(app)
    email = email or f"j{os.urandom(3).hex()}@ex.com"
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": email, "password": "palmreader1", "csrf": tok})
    return c


def test_create_returns_job_and_completes_sync():
    c = _client()
    r = c.post("/api/v1/readings", json={"image": _durl("good"), "hand": "right"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert job_id and r.json()["status"] == "queued"
    s = c.get(f"/api/v1/readings/{job_id}").json()
    assert s["status"] == "complete" and s["progress"] == 100
    res = s["result"]
    assert res["reading"]["title"] and len(res["comic"]["panels"]) == 4
    assert res["providers"]["vision"] == "mock"


def test_bad_image_rejected_without_job():
    c = _client()
    r = c.post("/api/v1/readings", json={"image": _durl("dark")})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected" and body["job_id"] is None
    assert body["quality"]["usable"] is False


def test_status_requires_auth_and_ownership():
    a = _client("owner@ex.com")
    job_id = a.post("/api/v1/readings", json={"image": _durl("good")}).json()["job_id"]
    # anonymous
    anon = TestClient(app)
    assert anon.get(f"/api/v1/readings/{job_id}", follow_redirects=False).status_code in (303, 307, 401, 403)
    # a different user → 404 (existence not leaked)
    b = _client("intruder@ex.com")
    assert b.get(f"/api/v1/readings/{job_id}").status_code == 404


def test_unknown_job_is_404():
    c = _client()
    assert c.get("/api/v1/readings/does-not-exist").status_code == 404


def test_async_path_polls_to_completion():
    os.environ["JOBS_SYNC"] = "false"   # exercise the real background thread
    try:
        c = _client()
        job_id = c.post("/api/v1/readings", json={"image": _durl("good")}).json()["job_id"]
        deadline = time.time() + 8
        status = None
        while time.time() < deadline:
            status = c.get(f"/api/v1/readings/{job_id}").json()
            if status["status"] in ("complete", "failed"):
                break
            time.sleep(0.2)
        assert status and status["status"] == "complete"
        assert status["result"]["comic"]["panels"]
    finally:
        os.environ["JOBS_SYNC"] = "true"
