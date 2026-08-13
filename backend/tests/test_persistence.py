"""Phase 12: readings persist as records; history/detail/delete/export/account."""
import base64
import io
import os
import re
import tempfile

import numpy as np
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "persist.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DEV_MOCK_AI"] = "true"
os.environ["JOBS_SYNC"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def _durl():
    rng = np.random.default_rng(0)
    arr = rng.integers(90, 190, size=(480, 640, 3), dtype=np.uint8)
    buf = io.BytesIO(); Image.fromarray(arr, "RGB").save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _client(email=None):
    c = TestClient(app)
    email = email or f"pz{os.urandom(3).hex()}@ex.com"
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": email, "password": "palmreader1", "csrf": tok})
    return c


def _csrf(c, path="/settings"):
    return re.search(r'name="csrf" value="([^"]+)"', c.get(path).text).group(1)


def _make_reading(c):
    job = c.post("/api/v1/readings", json={"image": _durl()}).json()["job_id"]
    return c.get(f"/api/v1/readings/{job}").json()["reading_id"]


def test_completed_job_persists_reading_and_shows_in_history():
    c = _client()
    rid = _make_reading(c)
    assert rid
    hist = c.get("/history").text
    assert "Open" in hist and "/reading/" + rid in hist


def test_reading_detail_renders_real_data_and_comic():
    c = _client()
    rid = _make_reading(c)
    page = c.get(f"/reading/{rid}").text
    assert "data:image/svg+xml" in page and ("Your nature" in page or "How you think" in page)
    assert "data:image/svg+xml" in page  # real comic panel images embedded


def test_detail_is_owner_only():
    a = _client("owner2@ex.com")
    rid = _make_reading(a)
    b = _client("intruder2@ex.com")
    assert b.get(f"/reading/{rid}").status_code == 404


def test_delete_one_reading():
    c = _client()
    rid = _make_reading(c)
    c.post(f"/reading/{rid}/delete", data={"csrf": _csrf(c, f"/reading/{rid}")}, follow_redirects=False)
    assert c.get(f"/reading/{rid}").status_code == 404


def test_export_returns_json_attachment():
    c = _client()
    _make_reading(c)
    r = c.get("/settings/export")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.json()
    assert "readings" in body and len(body["readings"]) == 1


def test_delete_all_and_delete_account():
    c = _client("gone@ex.com")
    _make_reading(c); _make_reading(c)
    c.post("/settings/delete-all", data={"csrf": _csrf(c)}, follow_redirects=False)
    assert len(c.get("/settings/export").json()["readings"]) == 0
    # delete account → logged out, protected pages redirect
    c.post("/account/delete", data={"csrf": _csrf(c)}, follow_redirects=False)
    assert c.get("/history", follow_redirects=False).status_code == 303
