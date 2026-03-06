from sqlalchemy import Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RookieBucket(Base):
    """
    Default feature values per (draft_round, position) for early-season weeks 1-3
    when a player has no prior-season state (rookie or new entrant).

    Seeded from ml/data/rookie_buckets.csv.
    Keys: draft_round (0=UDFA, 1-7=draft rounds) × pos (WR/TE).
    """

    __tablename__ = "rookie_buckets"
    __table_args__ = (
        UniqueConstraint("draft_round", "pos", name="uq_rookie_bucket"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_round: Mapped[int] = mapped_column(Integer, nullable=False)
    pos: Mapped[str] = mapped_column(String(5), nullable=False)

    # All CARRY_FEATURES — same columns as player_season_state feature values
    targets_pg: Mapped[float | None] = mapped_column(Float)
    yards_pg: Mapped[float | None] = mapped_column(Float)
    receptions_pg: Mapped[float | None] = mapped_column(Float)
    roll3_targets: Mapped[float | None] = mapped_column(Float)
    roll3_yards: Mapped[float | None] = mapped_column(Float)
    roll3_receptions: Mapped[float | None] = mapped_column(Float)
    lag_targets: Mapped[float | None] = mapped_column(Float)
    lag_yards: Mapped[float | None] = mapped_column(Float)
    target_share: Mapped[float | None] = mapped_column(Float)
    roll3_long_rec: Mapped[float | None] = mapped_column(Float)
    roll3_target_std: Mapped[float | None] = mapped_column(Float)
    tds_last3: Mapped[float | None] = mapped_column(Float)
    td_streak: Mapped[float | None] = mapped_column(Float)
    td_rate_eb: Mapped[float | None] = mapped_column(Float)
    td_rate_eb_std: Mapped[float | None] = mapped_column(Float)
    lag_snap_pct: Mapped[float | None] = mapped_column(Float)
    roll3_snap_pct: Mapped[float | None] = mapped_column(Float)
    roll3_rz_targets: Mapped[float | None] = mapped_column(Float)
    rz_target_share: Mapped[float | None] = mapped_column(Float)
    rz_td_rate_eb: Mapped[float | None] = mapped_column(Float)

    def __repr__(self) -> str:
        return f"<RookieBucket round={self.draft_round} pos={self.pos}>"
