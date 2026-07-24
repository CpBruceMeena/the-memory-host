"""Session model — represents a single game session."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.round import Round


class Session(UUIDMixin, TimestampMixin, Base):
    """A game session for a single player."""

    __tablename__ = "sessions"

    player_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    # 'active' | 'completed' | 'interrupted'

    score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    current_round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    max_rounds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10
    )

    room_url: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    room_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    ended_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True
    )

    # Relationships
    rounds: Mapped[list["Round"]] = relationship(
        "Round", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id}, player={self.player_name}, "
            f"status={self.status}, score={self.score}, "
            f"round={self.current_round})>"
        )
