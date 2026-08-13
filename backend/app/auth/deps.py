"""Auth dependencies. `get_current_user` is optional (for nav state);
`require_user` enforces login and triggers a redirect to /login."""
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import User


class NotAuthenticated(Exception):
    """Raised by require_user; handled by a redirect to /login."""


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if user is None:
        raise NotAuthenticated()
    return user
