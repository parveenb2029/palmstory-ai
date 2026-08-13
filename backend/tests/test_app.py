"""Phase 14: app-level integration + gap-filling tests (run fully on mocks)."""
import base64
import io
import os
import re
import tempfile

from PIL import Image, ImageDraw

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "app.db")

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def _photo():
    img = Image.new("RGB", (640, 480), (60, 50, 70))
    d = ImageDraw.Draw(img)
    for i in range(0, 640, 30):
        d.line([(i, 0), (i + 80, 480)], fill=(210, 180, 120), width=6)
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _register(c, email):
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": email, "password": "palmreader1", "csrf": tok})


def test_healthz_reports_status_and_providers():
    body = TestClient(app).get("/healthz").json()
    assert body["status"] == "ok"
    assert body["providers"]["vision"] == "mock"


def test_public_pages_render():
    c = TestClient(app)
    assert "Discover the story in your palm" in c.get("/").text
    assert "handled with care" in c.get("/privacy").text.lower() or c.get("/privacy").status_code == 200


def test_unknown_route_is_404():
    assert TestClient(app).get("/no-such-page").status_code == 404


def test_end_to_end_happy_path():
    c = TestClient(app)
    _register(c, "e2e@ex.com")
    # create a reading (job completes inline under JOBS_SYNC)
    job = c.post("/api/v1/readings", json={"image": _photo(), "hand": "right"})
    assert job.status_code == 202
    job_id = job.json()["job_id"]
    status = c.get(f"/api/v1/readings/{job_id}").json()
    assert status["status"] == "complete"
    rid = status["reading_id"]
    # it appears in history and renders on the detail page with a comic
    assert f"/reading/{rid}" in c.get("/history").text
    detail = c.get(f"/reading/{rid}").text
    assert "data:image/svg+xml" in detail  # rendered comic panels
    # export contains it, then delete removes it
    assert len(c.get("/settings/export").json()["readings"]) == 1
    tok = re.search(r'name="csrf" value="([^"]+)"', detail).group(1)
    c.post(f"/reading/{rid}/delete", data={"csrf": tok}, follow_redirects=False)
    assert c.get(f"/reading/{rid}").status_code == 404
