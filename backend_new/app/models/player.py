from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Player(Base):
    """
    Canonical player identity — written by roster sync, rarely mutated.
    Tank01 numeric player_id is the system-wide canonical key.
    """

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    position: Mapped[str] = mapped_column(String(10), nullable=False)  # 'WR' or 'TE'
    team: Mapped[Optional[str]] = mapped_column(String(10))  # current team abbreviation
    is_te: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draft_round: Mapped[Optional[int]] = mapped_column(Integer)  # 0 = UDFA, NULL = unknown
    experience: Mapped[Optional[int]] = mapped_column(Integer)  # years in NFL, 0 = rookie
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    headshot_url: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    game_logs: Mapped[list["PlayerGameLog"]] = relationship(back_populates="player")
    features: Mapped[list["PlayerFeatures"]] = relationship(back_populates="player")
    season_states: Mapped[list["PlayerSeasonState"]] = relationship(back_populates="player")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="player")
    odds: Mapped[list["SportsbookOdds"]] = relationship(back_populates="player")

    def __repr__(self) -> str:
        return f"<Player {self.player_id} {self.full_name} ({self.team})>"
