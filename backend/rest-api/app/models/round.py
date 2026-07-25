"""Round model — represents a single round within a game session."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.session import Session


class Round(UUIDMixin, TimestampMixin, Base):
    """A single round within a game session."""

    __tablename__ = "rounds"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    word_sequence: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False
    )
    # e.g. ["apple", "banana", "cat"]

    user_response: Mapped[Optional[list[str]]] = mapped_column(
        JSONB, nullable=True
    )
    # e.g. ["apple", "banana", "cat"]; NULL if not yet answered

    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True
    )
    # NULL = pending, TRUE = correct, FALSE = wrong

    answered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    session: Mapped["Session"] = relationship(
        "Session", back_populates="rounds"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "round_number",
            name="uq_session_round",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Round(id={self.id}, session={self.session_id}, "
            f"round={self.round_number}, "
            f"correct={self.is_correct})>"
        )
