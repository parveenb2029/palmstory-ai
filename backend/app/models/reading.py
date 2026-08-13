import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


def _now():
    return datetime.now(timezone.utc)


class Reading(Base):
    """A completed reading, owned by a user. `data_json` holds the full result
    (reading + interpretation + comic, etc.). The raw palm image is NOT stored."""
    __tablename__ = "readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="")
    hand: Mapped[str] = mapped_column(String(10), default="right")
    summary: Mapped[str] = mapped_column(String(500), default="")
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
