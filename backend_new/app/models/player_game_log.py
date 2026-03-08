from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayerGameLog(Base):
    """
    Raw box score stats per player per game.

    Tank01 supplies the core receiving stats. nflverse supplies snap
    count and red zone stats via the ID bridge (load_players()) — those columns
    are nullable and their presence is flagged in data_source_flags.

    Rows are written by ingest and never mutated after a game is final.
    """

    __tablename__ = "player_game_logs"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="uq_player_game_log"),
        Index("ix_player_game_logs_player_season_week", "player_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("games.game_id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Denormalized for query efficiency — avoids joining games on every feature query
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[str] = mapped_column(String(10), nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Core box score — from Tank01
    targets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    receptions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rec_yards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rec_tds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    long_rec: Mapped[Optional[int]] = mapped_column(Integer)

    # Snap data — from nflverse via alias table (nullable: match failure → NULL + DQ event)
    snap_count: Mapped[Optional[int]] = mapped_column(Integer)
    snap_pct: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))

    # Red zone — from nflverse PBP (nullable: same reason)
    rz_targets: Mapped[Optional[int]] = mapped_column(Integer)
    rz_rec_tds: Mapped[Optional[int]] = mapped_column(Integer)  # TDs from plays originating ≤20yd

    # Audit: which sources successfully populated this row
    # e.g. {"tank01": true, "nflverse_snap": true, "nflverse_rz": false}
    data_source_flags: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="game_logs")
    game: Mapped["Game"] = relationship(back_populates="player_game_logs")

    def __repr__(self) -> str:
        return f"<PlayerGameLog {self.player_id} {self.game_id}>"
