"""Cross-platform / shareable guards: portable paths + valid deploy config."""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "dep.db")

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_healthz_ok_for_uptime_checks():
    body = TestClient(app).get("/healthz").json()
    assert body["status"] == "ok" and body["version"]


def test_procfile_and_render_start_commands():
    proc = open(os.path.join(ROOT, "Procfile")).read()
    assert "uvicorn backend.app.main:app" in proc and "$PORT" in proc
    render = open(os.path.join(ROOT, "render.yaml")).read()
    assert "startCommand:" in render and "$PORT" in render
    assert "healthCheckPath: /healthz" in render
    assert "generateValue: true" in render  # SECRET_KEY is generated, not hard-coded


def test_no_absolute_paths_in_source():
    bad = ("/home/", "/Users/", "C:\\", "/mnt/")
    for base in ("backend/app", "vision", "palmistry"):
        for dirpath, _, files in os.walk(os.path.join(ROOT, base)):
            if "__pycache__" in dirpath:
                continue
            for f in files:
                if not f.endswith(".py"):
                    continue
                text = open(os.path.join(dirpath, f), encoding="utf-8").read()
                for token in bad:
                    assert token not in text, f"{f} contains absolute path {token!r}"


def test_dockerfile_uses_port_env():
    df = open(os.path.join(ROOT, "Dockerfile")).read()
    assert "${PORT}" in df and "0.0.0.0" in df
