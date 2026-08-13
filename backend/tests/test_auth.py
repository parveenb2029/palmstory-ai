"""Phase 2 auth tests. Uses a throwaway SQLite DB and mock-free logic."""
import os, re, tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.auth.security import hash_password, verify_password  # noqa: E402

client = TestClient(app)


def _csrf(path):
    html = client.get(path).text
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_password_hashing_roundtrip():
    h = hash_password("correct horse battery")
    assert h != "correct horse battery"
    assert verify_password(h, "correct horse battery")
    assert not verify_password(h, "wrong")


def test_protected_route_redirects_when_anonymous():
    r = client.get("/history", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_register_login_logout_flow():
    token = _csrf("/register")
    r = client.post("/register", data={
        "name": "Ada", "email": "ada@example.com",
        "password": "supersecret", "csrf": token,
    }, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/history"
    # now authenticated → protected page renders
    assert client.get("/history").status_code == 200
    # logout
    token = _csrf("/history")
    client.post("/logout", data={"csrf": token}, follow_redirects=False)
    assert client.get("/history", follow_redirects=False).status_code == 303


def test_duplicate_and_bad_input_rejected():
    token = _csrf("/register")
    r = client.post("/register", data={"email": "ada@example.com", "password": "supersecret", "csrf": token})
    assert "already exists" in r.text
    token = _csrf("/register")
    r = client.post("/register", data={"email": "bad", "password": "supersecret", "csrf": token})
    assert "valid email" in r.text
    token = _csrf("/register")
    r = client.post("/register", data={"email": "x@y.com", "password": "short", "csrf": token})
    assert "between 8 and 128" in r.text


def test_csrf_required():
    r = client.post("/login", data={"email": "ada@example.com", "password": "supersecret", "csrf": "bogus"})
    assert "session expired" in r.text
