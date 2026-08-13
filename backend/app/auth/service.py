"""User account operations and input validation."""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.user import User
from .security import hash_password, verify_password

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
MIN_PASSWORD = 8


def valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def valid_password(password: str) -> bool:
    # cap the max length too: hashing an enormous password wastes CPU (DoS vector)
    return isinstance(password, str) and MIN_PASSWORD <= len(password) <= 128


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == (email or "").lower().strip()))


def create_user(db: Session, email: str, password: str, name: str = "") -> User:
    user = User(
        email=email.lower().strip(),
        name=(name or "").strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user and verify_password(user.password_hash, password):
        return user
    return None
