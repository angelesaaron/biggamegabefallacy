from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TeamGameStats(Base):
    """
    Aggregated team totals per game.

    Derived from player_game_logs by the ingest pipeline after all players
    for a completed game have been written. Enables target_share and
    rz_target_share to be computed as a pure SQL join — no Pandas needed.

    target_share = player_game_logs.targets / team_game_stats.team_targets
    rz_target_share = player_game_logs.rz_targets / team_game_stats.team_rz_targets
    """

    __tablename__ = "team_game_stats"
    __table_args__ = (
        UniqueConstraint("game_id", "team", name="uq_team_game_stats"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("games.game_id", ondelete="CASCADE"), nullable=False, index=True
    )
    team: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Denormalized for query efficiency
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)

    team_targets: Mapped[int] = mapped_column(Integer, nullable=False)
    team_rec_tds: Mapped[int] = mapped_column(Integer, nullable=False)

    # Nullable: only populated when nflverse RZ data is available for the game
    team_rz_targets: Mapped[Optional[int]] = mapped_column(Integer)           # WR/TE only
    team_rz_tds: Mapped[Optional[int]] = mapped_column(Integer)               # WR/TE only
    # All-position RZ targets — correct denominator for rz_target_share (matches training)
    team_rz_targets_all_pos: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    game: Mapped["Game"] = relationship(back_populates="team_game_stats")

    def __repr__(self) -> str:
        return f"<TeamGameStats {self.team} {self.game_id}>"
