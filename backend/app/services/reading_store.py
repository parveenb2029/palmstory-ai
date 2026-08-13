"""Owner-scoped operations on stored readings. Every function is filtered by
user_id so one user can never touch another's readings."""
import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models.reading import Reading


def list_for_user(db: Session, user_id: str):
    return db.scalars(
        select(Reading).where(Reading.user_id == user_id).order_by(Reading.created_at.desc())
    ).all()


def get_for_user(db: Session, user_id: str, reading_id: str):
    r = db.get(Reading, reading_id)
    return r if (r and r.user_id == user_id) else None


def create(db: Session, user_id: str, hand: str, result: dict) -> Reading:
    reading = result.get("reading", {})
    r = Reading(
        user_id=user_id,
        title=reading.get("title", "A palm reading")[:200],
        hand=hand,
        summary=reading.get("snapshot", "")[:500],
        data_json=json.dumps(result),
    )
    db.add(r)
    db.flush()          # assign id without committing the whole txn yet
    return r


def delete_for_user(db: Session, user_id: str, reading_id: str) -> bool:
    r = get_for_user(db, user_id, reading_id)
    if not r:
        return False
    db.delete(r)
    db.commit()
    return True


def delete_all_for_user(db: Session, user_id: str) -> int:
    n = db.execute(delete(Reading).where(Reading.user_id == user_id)).rowcount
    db.commit()
    return n or 0


def export_for_user(db: Session, user_id: str) -> list:
    return [json.loads(r.data_json) for r in list_for_user(db, user_id)]
