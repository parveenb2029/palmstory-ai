"""PalmStory AI — application entry.

Phase 1: UI foundation (mock reading data).
Phase 2: authentication — real users (Argon2), secure sessions, CSRF, and
route protection. Local dev uses SQLite (zero setup); set DATABASE_URL for
Postgres in production. Run:

    pip install -r requirements.txt
    uvicorn backend.app.main:app --reload
    # open http://localhost:8000
"""
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import get_db, init_db, SessionLocal
from .security import SecurityHeadersMiddleware
from .auth import service as auth_service
from .auth.deps import NotAuthenticated, get_current_user, require_user
from .auth.security import check_csrf, ensure_csrf
from .models.user import User
from .services import reading_store
from .api.vision import router as vision_router
from .api.readings import router as readings_router

BASE = Path(__file__).resolve().parents[2]
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-change-me")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="PalmStory AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=os.getenv("SECURE_COOKIES", "false").strip().lower() in ("1", "true", "yes"),
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=600)


class _CachedStatic(StaticFiles):
    """Serve static assets with a cache header (perf: browser re-use)."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers.setdefault("Cache-Control", "public, max-age=3600")
        return resp


app.mount("/static", _CachedStatic(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "frontend" / "templates"))

# Ensure tables exist immediately (idempotent); lifespan also runs this on the
# real server. This keeps `uvicorn` and the test client both working.
init_db()

app.include_router(vision_router)
app.include_router(readings_router)


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request: Request, exc: NotAuthenticated):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    return RedirectResponse("/login", status_code=303)


def _user_for(request: Request):
    try:
        uid = request.session.get("user_id")
        if uid:
            db = SessionLocal()
            try:
                return db.get(User, uid)
            finally:
                db.close()
    except Exception:
        return None
    return None


@app.exception_handler(StarletteHTTPException)
async def _http_exception(request: Request, exc: StarletteHTTPException):
    # API paths get JSON; page routes get a friendly HTML error page.
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    messages = {404: "Page not found", 403: "You don't have access to that", 405: "That action isn't allowed"}
    message = messages.get(exc.status_code, exc.detail or "Something went wrong")
    return templates.TemplateResponse(
        request, "error.html",
        {"code": exc.status_code, "message": message,
         "current_user": _user_for(request), "csrf_token": ""},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Internal server error."}, status_code=500)
    return templates.TemplateResponse(
        request, "error.html",
        {"code": 500, "message": "Something went wrong on our end",
         "current_user": _user_for(request), "csrf_token": ""},
        status_code=500,
    )


def render(template_name: str, request: Request, user: Optional[User] = None, **ctx):
    ctx["current_user"] = user
    ctx["csrf_token"] = ensure_csrf(request)
    return templates.TemplateResponse(request, template_name, ctx)


# ---------------------------------------------------------------- public pages
@app.get("/", response_class=HTMLResponse)
def landing(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render("landing.html", request, user, page="home")


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render("privacy.html", request, user, page="privacy")


@app.get("/healthz")
def healthz():
    from .providers import active_providers
    return {"status": "ok", "version": "1.0.0", "providers": active_providers()}


# ---------------------------------------------------------------- auth
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    if user:
        return RedirectResponse("/history", status_code=303)
    return render("login.html", request, None, page="login")


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, email: str = Form(""), password: str = Form(""),
                 csrf: str = Form(""), db: Session = Depends(get_db)):
    if not check_csrf(request, csrf):
        return render("login.html", request, None, page="login", error="Your session expired — please try again.", email=email)
    user = auth_service.authenticate(db, email, password)
    if not user:
        return render("login.html", request, None, page="login", error="Email or password is incorrect.", email=email)
    request.session["user_id"] = user.id
    return RedirectResponse("/history", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    if user:
        return RedirectResponse("/history", status_code=303)
    return render("register.html", request, None, page="register")


@app.post("/register", response_class=HTMLResponse)
def register_submit(request: Request, name: str = Form(""), email: str = Form(""),
                    password: str = Form(""), csrf: str = Form(""), db: Session = Depends(get_db)):
    def fail(msg):
        return render("register.html", request, None, page="register", error=msg, name=name, email=email)

    if not check_csrf(request, csrf):
        return fail("Your session expired — please try again.")
    if len(email) > 255 or len(name) > 120:
        return fail("That's too long — please shorten your details.")
    if not auth_service.valid_email(email):
        return fail("Please enter a valid email address.")
    if not auth_service.valid_password(password):
        return fail("Password must be between 8 and 128 characters.")
    if auth_service.get_user_by_email(db, email):
        return fail("An account with that email already exists.")
    user = auth_service.create_user(db, email, password, name)
    request.session["user_id"] = user.id
    return RedirectResponse("/history", status_code=303)


@app.post("/logout")
def logout(request: Request, csrf: str = Form("")):
    if check_csrf(request, csrf):
        request.session.pop("user_id", None)
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------- protected pages
@app.get("/capture", response_class=HTMLResponse)
def capture(request: Request, user: User = Depends(require_user)):
    return render("capture.html", request, user, page="capture")


@app.get("/reading/{reading_id}", response_class=HTMLResponse)
def reading_detail(reading_id: str, request: Request, user: User = Depends(require_user),
                   db: Session = Depends(get_db)):
    rec = reading_store.get_for_user(db, user.id, reading_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Reading not found.")
    data = json.loads(rec.data_json)
    reading = data.get("reading", {})
    interp = data.get("interpretation", {})
    comic = data.get("comic", {})
    ctx = {
        "reading_id": rec.id,
        "title": reading.get("title", "Your palm story"),
        "hand": data.get("hand", rec.hand),
        "created": rec.created_at.strftime("%d %b %Y"),
        "snapshot": reading.get("snapshot", ""),
        "facets": [{"tradition": f["tradition"], "detected": f["detected"],
                    "conf": f["detection_confidence"], "note": f["interpretations"][0]}
                   for f in interp.get("facets", [])],
        "sections": reading.get("sections", {}),
        "strengths": reading.get("strengths", []),
        "challenges": reading.get("challenges", []),
        "themes": reading.get("themes", []),
        "story": reading.get("story", ""),
        "comic_title": comic.get("title", ""),
        "comic_panels": comic.get("panels", []),
    }
    return render("reading.html", request, user, page="reading", r=ctx)


@app.post("/reading/{reading_id}/delete")
def reading_delete(reading_id: str, request: Request, csrf: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    if check_csrf(request, csrf):
        reading_store.delete_for_user(db, user.id, reading_id)
    return RedirectResponse("/history", status_code=303)


@app.get("/history", response_class=HTMLResponse)
def history(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    items = reading_store.list_for_user(db, user.id)
    return render("history.html", request, user, page="history", items=items)


@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    count = len(reading_store.list_for_user(db, user.id))
    return render("settings.html", request, user, page="settings", reading_count=count)


@app.get("/settings/export")
def settings_export(user: User = Depends(require_user), db: Session = Depends(get_db)):
    data = reading_store.export_for_user(db, user.id)
    payload = json.dumps({"account": user.email, "readings": data}, indent=2)
    return Response(content=payload, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="palmstory-export.json"'})


@app.post("/settings/delete-all")
def settings_delete_all(request: Request, csrf: str = Form(""),
                        user: User = Depends(require_user), db: Session = Depends(get_db)):
    if check_csrf(request, csrf):
        reading_store.delete_all_for_user(db, user.id)
    return RedirectResponse("/settings", status_code=303)


@app.post("/account/delete")
def account_delete(request: Request, csrf: str = Form(""),
                   user: User = Depends(require_user), db: Session = Depends(get_db)):
    if check_csrf(request, csrf):
        from .models.job import Job
        from sqlalchemy import delete as sa_delete
        reading_store.delete_all_for_user(db, user.id)
        db.execute(sa_delete(Job).where(Job.user_id == user.id))
        db.delete(user)
        db.commit()
        request.session.pop("user_id", None)
    return RedirectResponse("/", status_code=303)
