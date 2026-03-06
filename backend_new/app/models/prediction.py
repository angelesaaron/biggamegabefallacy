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


class Prediction(Base):
    """
    One row per player per week. Model output. Immutable after creation.

    raw_prob  → XGBoost output before calibration
    calibrated_prob → post-calibration (temperature or beta)
    week_scalar → early-season adjustment scalar (1.0 for weeks 4+)
    final_prob  → calibrated_prob × week_scalar — what the UI shows

    model_odds / favor are NOT stored here. They are computed at query
    time from final_prob (they are math, not data).

    feature_row_id is a hard FK to the exact PlayerFeatures row that
    drove this prediction — full auditability.
    """

    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "week", "model_version",
            name="uq_prediction",
        ),
        Index("ix_predictions_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)

    # FK to the exact feature row that drove this prediction
    feature_row_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("player_features.id", ondelete="SET NULL")
    )

    raw_prob: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    calibrated_prob: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)
    week_scalar: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.0)
    final_prob: Mapped[float] = mapped_column(Numeric(6, 5), nullable=False)

    completeness_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2))
    is_low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="predictions")
    feature_row: Mapped[Optional["PlayerFeatures"]] = relationship(back_populates="predictions")

    def __repr__(self) -> str:
        return (
            f"<Prediction {self.player_id} S{self.season}W{self.week} "
            f"{self.final_prob:.3f} [{self.model_version}]>"
        )
