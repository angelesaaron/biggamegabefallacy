from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SportsbookOdds(Base):
    """
    Sportsbook odds per player per game per book.

    implied_prob is computed from American odds on write:
        p = 1 / (1 + 100 / abs(odds))   for positive odds
        p = abs(odds) / (abs(odds) + 100) for negative odds
    Stored so UI edge calc (model_prob vs market_prob) is a direct
    numeric comparison — no conversion at query time.

    Tank01 returns a single consensus line, stored as sportsbook='consensus'.
    """

    __tablename__ = "sportsbook_odds"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", "sportsbook", name="uq_sportsbook_odds"),
        Index("ix_sportsbook_odds_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("games.game_id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    sportsbook: Mapped[str] = mapped_column(String(30), nullable=False)  # 'consensus', 'draftkings', etc.
    odds: Mapped[int] = mapped_column(Integer, nullable=False)  # American format e.g. +250, -150
    implied_prob: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="odds")
    game: Mapped["Game"] = relationship(back_populates="odds")

    def __repr__(self) -> str:
        return f"<SportsbookOdds {self.player_id} {self.game_id} {self.sportsbook} {self.odds:+d}>"
