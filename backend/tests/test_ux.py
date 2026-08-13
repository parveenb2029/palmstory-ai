"""Phase 17: custom error pages (HTML for pages, JSON for API) + a11y bits."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "ux.db")

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402


def test_page_404_renders_friendly_html():
    r = TestClient(app).get("/definitely-not-a-page")
    assert r.status_code == 404
    assert "Page not found" in r.text and "Read my palm" in r.text


def test_api_404_returns_json():
    c = TestClient(app)
    # unknown API path → JSON, not HTML
    r = c.get("/api/v1/readings/nonexistent-job")
    assert r.status_code in (401, 403, 404)
    assert r.headers["content-type"].startswith("application/json")


def test_skip_link_and_favicon_present():
    c = TestClient(app)
    home = c.get("/").text
    assert 'class="skip-link"' in home and 'id="main"' in home
    assert '/static/favicon.svg' in home
    assert c.get("/static/favicon.svg").status_code == 200
