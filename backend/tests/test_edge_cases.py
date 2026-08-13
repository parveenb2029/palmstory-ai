"""Hardening pass: image edge cases + form validation. Every case must be
handled gracefully — never a 500, never a fabricated reading."""
import base64
import io
import math
import os
import re
import tempfile

from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "edge.db")
os.environ["DEV_MOCK_AI"] = "true"
os.environ["JOBS_SYNC"] = "true"
os.environ["RATE_LIMIT_READINGS_PER_HOUR"] = "500"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402
from vision.quality.quality import assess  # noqa: E402
from vision.palm_detection.detect import detect  # noqa: E402


def _durl(img, fmt="JPEG"):
    b = io.BytesIO(); img.save(b, format=fmt)
    mt = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}[fmt]
    return f"data:image/{mt};base64," + base64.b64encode(b.getvalue()).decode()


def _client():
    c = TestClient(app)
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": f"e{os.urandom(3).hex()}@ex.com", "password": "palmreader1", "csrf": tok})
    return c


def _all_finite(d):
    return all((not isinstance(v, float)) or math.isfinite(v) for v in d.values())


def test_quality_and_detection_finite_on_degenerate_sizes():
    for size in [(1, 1), (2, 2), (3, 3), (1, 640), (640, 1)]:
        img = Image.new("RGB", size, (150, 150, 150))
        q, d = assess(img), detect(img)
        assert _all_finite(q), (size, q)
        assert _all_finite(d), (size, d)


def test_endpoint_never_500s_on_odd_images():
    c = _client()
    imgs = {
        "1x1": _durl(Image.new("RGB", (1, 1), (150, 150, 150))),
        "2x2": _durl(Image.new("RGB", (2, 2), (150, 150, 150))),
        "rgba": _durl(Image.new("RGBA", (640, 480), (200, 165, 135, 128)), "PNG"),
        "cmyk": _durl(Image.new("CMYK", (640, 480), (0, 20, 40, 10)).convert("RGB")),
        "webp": _durl(Image.new("RGB", (640, 480), (200, 165, 135)), "WEBP"),
        "dark": _durl(Image.new("RGB", (640, 480), (8, 8, 8))),
        "bright": _durl(Image.new("RGB", (640, 480), (252, 252, 252))),
    }
    for name, d in imgs.items():
        r = c.post("/api/v1/readings", json={"image": d})
        assert r.status_code < 500, (name, r.status_code)


def test_malformed_images_are_4xx_not_500():
    c = _client()
    for bad in ["data:image/jpeg;base64,notbase64@@@",
                "data:image/jpeg;base64," + base64.b64encode(b"not an image").decode(),
                "data:image/jpeg;base64,",
                "data:text/plain;base64,QUJD"]:
        assert c.post("/api/v1/readings", json={"image": bad}).status_code < 500


def test_bad_palm_photos_are_rejected_with_reasons():
    c = _client()
    dark = c.post("/api/v1/readings", json={"image": _durl(Image.new("RGB", (640, 480), (8, 8, 8)))}).json()
    assert dark["status"] == "rejected" and dark["job_id"] is None
    assert any("dark" in r.lower() for r in dark["quality"]["reasons"])


def test_registration_field_limits():
    c = TestClient(app)
    tok = lambda: re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    # oversized password (DoS guard)
    r = c.post("/register", data={"email": "a@b.com", "password": "x" * 5000, "csrf": tok()})
    assert "between 8 and 128" in r.text
    # angle-bracket email rejected by format check
    r = c.post("/register", data={"email": "<script>@x.com", "password": "palmreader1", "csrf": tok()})
    assert "valid email" in r.text
    # oversized name
    r = c.post("/register", data={"name": "n" * 500, "email": "a@b.com", "password": "palmreader1", "csrf": tok()})
    assert "too long" in r.text


def test_templates_autoescape_active():
    # Jinja autoescaping is on for .html — a crafted value renders escaped, not raw.
    from backend.app.main import templates
    out = templates.env.from_string("{{ x }}").render(x="<script>alert(1)</script>")
    assert "<script>" not in out and "&lt;script&gt;" in out
