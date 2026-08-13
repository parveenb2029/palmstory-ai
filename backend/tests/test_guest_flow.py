"""Guest flow: one free full reading without login; sign up for more + Q&A."""
import base64
import io
import os
import re
import tempfile

from PIL import Image, ImageDraw

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "guest.db")
os.environ["DEV_MOCK_AI"] = "true"
os.environ["JOBS_SYNC"] = "true"
os.environ["RATE_LIMIT_READINGS_PER_HOUR"] = "500"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def _durl():
    img = Image.new("RGB", (640, 480), (70, 55, 45))
    d = ImageDraw.Draw(img); d.ellipse([120, 80, 520, 440], fill=(200, 165, 135))
    for x in (200, 270, 340, 410):
        d.rectangle([x, 40, x + 40, 120], fill=(200, 165, 135))
    b = io.BytesIO(); img.save(b, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def _register(c, email):
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": email, "password": "palmreader1", "csrf": tok})


def test_capture_page_is_public():
    assert TestClient(app).get("/capture").status_code == 200


def test_guest_gets_one_free_reading_then_signup_required():
    c = TestClient(app)
    first = c.post("/api/v1/readings", json={"image": _durl()})
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    # guest can view their own result page (full reading), no login
    assert c.get(f"/result/{job_id}").status_code == 200
    # second reading is gated
    second = c.post("/api/v1/readings", json={"image": _durl()})
    assert second.status_code == 200 and second.json()["status"] == "signup_required"


def test_guest_result_shows_full_comic_and_signup_cta():
    c = TestClient(app)
    job_id = c.post("/api/v1/readings", json={"image": _durl()}).json()["job_id"]
    page = c.get(f"/result/{job_id}").text
    assert "data:image/svg+xml" in page          # full comic panels present
    assert "Sign up" in page                      # sign-up CTA for guest
    assert "Delete this reading" not in page       # no owner-only controls


def test_guest_cannot_view_another_guests_result():
    a = TestClient(app)
    job_id = a.post("/api/v1/readings", json={"image": _durl()}).json()["job_id"]
    b = TestClient(app)  # different browser/session
    assert b.get(f"/result/{job_id}").status_code == 404


def test_guest_reading_is_not_persisted_to_history():
    c = TestClient(app)
    job_id = c.post("/api/v1/readings", json={"image": _durl()}).json()["job_id"]
    status = c.get(f"/api/v1/readings/{job_id}").json()
    assert status["status"] == "complete"
    assert status["reading_id"] is None          # guests don't get saved history


def test_logged_in_user_still_persists_and_sees_history():
    c = TestClient(app)
    _register(c, "member@ex.com")
    job_id = c.post("/api/v1/readings", json={"image": _durl()}).json()["job_id"]
    status = c.get(f"/api/v1/readings/{job_id}").json()
    assert status["reading_id"]                    # saved
    assert f"/reading/{status['reading_id']}" in c.get("/history").text
    # members are not limited to one
    assert c.post("/api/v1/readings", json={"image": _durl()}).status_code == 202
