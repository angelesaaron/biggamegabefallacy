from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayerSeasonState(Base):
    """
    End-of-season carry-forward state — replaces prior_season_final_state.csv.

    Written by the end-of-season job using the player's final-week features.
    Read by the feature pipeline for weeks 1-3 (is_early_season=True) when
    no in-season game logs exist yet.

    join_season = season + 1: the season this row is consumed for.
    """

    __tablename__ = "player_season_state"
    __table_args__ = (
        UniqueConstraint("player_id", "season", name="uq_player_season_state"),
        Index("ix_player_season_state_join_season", "join_season"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    join_season: Mapped[int] = mapped_column(Integer, nullable=False)  # season + 1
    team: Mapped[Optional[str]] = mapped_column(String(10))
    draft_round: Mapped[Optional[int]] = mapped_column(Integer)

    # ── Carry-forward feature values ────────────────────────────────────────
    targets_pg: Mapped[Optional[float]] = mapped_column(Numeric)
    yards_pg: Mapped[Optional[float]] = mapped_column(Numeric)
    receptions_pg: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_targets: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_yards: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_receptions: Mapped[Optional[float]] = mapped_column(Numeric)
    lag_targets: Mapped[Optional[float]] = mapped_column(Numeric)
    lag_yards: Mapped[Optional[float]] = mapped_column(Numeric)
    target_share: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_long_rec: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_target_std: Mapped[Optional[float]] = mapped_column(Numeric)
    tds_last3: Mapped[Optional[float]] = mapped_column(Numeric)
    td_streak: Mapped[Optional[int]] = mapped_column(Integer)
    td_rate_eb: Mapped[Optional[float]] = mapped_column(Numeric)
    td_rate_eb_std: Mapped[Optional[float]] = mapped_column(Numeric)
    lag_snap_pct: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_snap_pct: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_rz_targets: Mapped[Optional[float]] = mapped_column(Numeric)
    rz_target_share: Mapped[Optional[float]] = mapped_column(Numeric)
    rz_td_rate_eb: Mapped[Optional[float]] = mapped_column(Numeric)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="season_states")

    def __repr__(self) -> str:
        return f"<PlayerSeasonState {self.player_id} S{self.season} → {self.join_season}>"
