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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayerFeatures(Base):
    """
    Pre-computed model features — the architectural centrepiece of v2.

    Prediction is no longer "compute features on the fly at request time."
    It is "read a pre-validated row from this table, run inference, done."

    Feature computation runs as a discrete pipeline step after game log
    ingest completes. Each row is validated (completeness_score) and
    stamped with feature_version so history is never destroyed on
    re-computation.

    Predictions with completeness_score < 0.75 are flagged low-confidence.

    feature_version examples: 'v2', 'v2.1'
    """

    __tablename__ = "player_features"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "week", "feature_version",
            name="uq_player_features",
        ),
        Index("ix_player_features_lookup", "player_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_version: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── Usage volume ────────────────────────────────────────────────────────
    targets_pg: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_targets: Mapped[Optional[float]] = mapped_column(Numeric)
    yards_pg: Mapped[Optional[float]] = mapped_column(Numeric)
    receptions_pg: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_yards: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_receptions: Mapped[Optional[float]] = mapped_column(Numeric)
    lag_targets: Mapped[Optional[float]] = mapped_column(Numeric)
    lag_yards: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Target share ────────────────────────────────────────────────────────
    target_share: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Downfield usage ─────────────────────────────────────────────────────
    roll3_long_rec: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Usage volatility ────────────────────────────────────────────────────
    roll3_target_std: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Streak / momentum ───────────────────────────────────────────────────
    tds_last3: Mapped[Optional[float]] = mapped_column(Numeric)
    td_streak: Mapped[Optional[int]] = mapped_column(Integer)

    # ── Empirical Bayes TD rates ─────────────────────────────────────────────
    td_rate_eb: Mapped[Optional[float]] = mapped_column(Numeric)
    td_rate_eb_std: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Player context ───────────────────────────────────────────────────────
    is_te: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Snap data (nullable: nflverse match may fail) ───────────────────────
    lag_snap_pct: Mapped[Optional[float]] = mapped_column(Numeric)
    roll3_snap_pct: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Red zone (nullable: nflverse PBP match may fail) ────────────────────
    roll3_rz_targets: Mapped[Optional[float]] = mapped_column(Numeric)
    rz_target_share: Mapped[Optional[float]] = mapped_column(Numeric)
    rz_td_rate_eb: Mapped[Optional[float]] = mapped_column(Numeric)

    # ── Metadata ─────────────────────────────────────────────────────────────
    is_early_season: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    carry_forward_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fraction of non-null features: 0.00–1.00
    completeness_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="features")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="feature_row")

    def __repr__(self) -> str:
        return f"<PlayerFeatures {self.player_id} S{self.season}W{self.week} v={self.feature_version}>"
