"""Readings endpoint (async contract, Phase 11): job → result carries the
observation/interpretation/reading. Uses JOBS_SYNC so the job completes inline."""
import base64
import io
import os
import re
import tempfile

import numpy as np
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "rd.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DEV_MOCK_AI"] = "true"
os.environ["JOBS_SYNC"] = "true"

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


def _client():
    c = TestClient(app)
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": f"r{os.urandom(3).hex()}@ex.com", "password": "palmreader1", "csrf": tok})
    return c


def _result(c, durl, hand="right"):
    jid = c.post("/api/v1/readings", json={"image": durl, "hand": hand}).json()["job_id"]
    return c.get(f"/api/v1/readings/{jid}").json()["result"]


def test_guest_can_read_without_login():
    # reading no longer requires an account — a guest gets one free reading
    r = TestClient(app).post("/api/v1/readings", json={"image": _durl("good")})
    assert r.status_code == 202 and r.json()["job_id"]


def test_good_image_yields_validated_observation():
    res = _result(_client(), _durl("good"), hand="left")
    assert res["hand"] == "left"
    assert res["quality"]["usable"] is True
    obs = res["observation"]
    assert obs and len(obs["observations"]) == 4
    for o in obs["observations"]:
        assert 0.0 <= o["confidence"] <= 1.0


def test_bad_image_gates_before_job():
    c = _client()
    r = c.post("/api/v1/readings", json={"image": _durl("dark")})
    assert r.json()["status"] == "rejected" and r.json()["job_id"] is None
    assert r.json()["quality"]["usable"] is False


def test_hand_defaults_and_normalizes():
    assert _result(_client(), _durl("good"), hand="L")["hand"] == "left"
    _client().post("/api/v1/readings", json={"image": _durl("good")})


def test_non_string_image_is_400_not_500():
    c = _client()
    for bad in [123, None, ["a"], {"x": 1}]:
        r = c.post("/api/v1/readings", json={"image": bad})
        assert r.status_code < 500, (bad, r.status_code)
