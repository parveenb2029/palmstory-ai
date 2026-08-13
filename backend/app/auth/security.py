"""Security primitives: Argon2 password hashing + CSRF tokens.

Passwords are NEVER stored in plaintext. Argon2id (via argon2-cffi) is used for
hashing; verification is constant-time on the library side.
"""
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False


# --- CSRF: a per-session token echoed by forms and checked on POST ---

def ensure_csrf(request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def check_csrf(request, token: str) -> bool:
    real = request.session.get("csrf", "")
    return bool(token) and bool(real) and secrets.compare_digest(token, real)
