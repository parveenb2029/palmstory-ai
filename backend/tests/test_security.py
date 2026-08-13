"""Phase 13: security headers, rate limiting, image hardening."""
import base64
import io
import os
import re
import tempfile

import numpy as np
from PIL import Image

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "sec.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DEV_MOCK_AI"] = "true"
os.environ["JOBS_SYNC"] = "true"
os.environ["RATE_LIMIT_READINGS_PER_HOUR"] = "3"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.security import RateLimiter  # noqa: E402


def _durl():
    rng = np.random.default_rng(0)
    arr = rng.integers(90, 190, size=(480, 640, 3), dtype=np.uint8)
    buf = io.BytesIO(); Image.fromarray(arr, "RGB").save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _client():
    c = TestClient(app)
    tok = re.search(r'name="csrf" value="([^"]+)"', c.get("/register").text).group(1)
    c.post("/register", data={"email": f"s{os.urandom(3).hex()}@ex.com", "password": "palmreader1", "csrf": tok})
    return c


def test_security_headers_present():
    r = _client().get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "camera=(self)" in r.headers["Permissions-Policy"]
    # CSP must allow the things the app actually uses
    csp = r.headers["Content-Security-Policy"]
    assert "https://fonts.gstatic.com" in csp and "image.pollinations.ai" in csp and "data:" in csp


def test_rate_limiter_unit():
    rl = RateLimiter(limit=2, window_seconds=3600)
    assert rl.allow("u") and rl.allow("u")
    assert not rl.allow("u")            # third blocked
    assert rl.allow("other")            # different key unaffected


def test_readings_rate_limited_after_limit():
    # fresh limiter state per process; limit=3 from env. Reset the shared limiter.
    from backend.app import security
    security.reading_rate_limiter = security.RateLimiter(limit=3, window_seconds=3600)
    # re-point the endpoint module reference
    import backend.app.api.readings as rd
    rd.reading_rate_limiter = security.reading_rate_limiter
    c = _client()
    codes = [c.post("/api/v1/readings", json={"image": _durl()}).status_code for _ in range(4)]
    assert codes[:3] == [202, 202, 202]
    assert codes[3] == 429


def test_decompression_bomb_rejected():
    # a small file that claims enormous dimensions is caught by MAX_IMAGE_PIXELS
    from backend.app import security
    security.reading_rate_limiter = security.RateLimiter(limit=50, window_seconds=3600)
    import backend.app.api.readings as rd
    rd.reading_rate_limiter = security.reading_rate_limiter
    big = Image.new("RGB", (8000, 8000), (120, 120, 120))
    buf = io.BytesIO(); big.save(buf, format="PNG")
    durl = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    r = _client().post("/api/v1/readings", json={"image": durl})
    assert r.status_code == 422
