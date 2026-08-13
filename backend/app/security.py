"""Security hardening: response headers + a simple per-user rate limiter.

The CSP is deliberately scoped to what the app actually uses: self, inline
styles (the templates use style="" attributes), Google Fonts, data: images (the
SVG comic panels), and the Pollinations image host for real comic images.
"""
import os
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https://image.pollinations.ai; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        # HSTS only matters over HTTPS; enable in production behind TLS
        if os.getenv("SECURE_COOKIES", "false").strip().lower() in ("1", "true", "yes"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class RateLimiter:
    """Fixed-window per-key limiter (in-process). For multi-process, back this
    with Redis — the call sites don't change."""

    def __init__(self, limit: int, window_seconds: int = 3600):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        dq = self._hits[key]
        while dq and dq[0] <= now - self.window:
            dq.popleft()
        if len(dq) >= self.limit:
            return False
        dq.append(now)
        return True


def readings_limit() -> int:
    try:
        return int(os.getenv("RATE_LIMIT_READINGS_PER_HOUR", "20"))
    except ValueError:
        return 20


reading_rate_limiter = RateLimiter(limit=readings_limit(), window_seconds=3600)
