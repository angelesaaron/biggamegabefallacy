from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Game(Base):
    """
    One row per NFL game. Written by schedule sync.
    game_id uses Tank01 format: YYYYMMDD_AWAY@HOME
    """

    __tablename__ = "games"

    game_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    week: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season_type: Mapped[str] = mapped_column(String(10), nullable=False)  # 'reg', 'post', 'pre'
    home_team: Mapped[str] = mapped_column(String(10), nullable=False)
    away_team: Mapped[str] = mapped_column(String(10), nullable=False)
    game_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )  # 'scheduled', 'final', 'in_progress'

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    player_game_logs: Mapped[list["PlayerGameLog"]] = relationship(back_populates="game")
    team_game_stats: Mapped[list["TeamGameStats"]] = relationship(back_populates="game")
    odds: Mapped[list["SportsbookOdds"]] = relationship(back_populates="game")

    def __repr__(self) -> str:
        return f"<Game {self.game_id} S{self.season}W{self.week}>"
