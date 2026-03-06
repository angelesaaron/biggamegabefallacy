from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DataQualityEvent(Base):
    """
    Replaces silent failures. Written by the ingest pipeline whenever
    something goes wrong that would produce a NULL feature or skip a
    prediction.

    A batch run summary queries this table to surface:
        "8 alias match failures this week — these players have null snap features."
    Fix the alias table, re-run the feature job, nulls go away.
    No more invisible model degradation.

    event_type values:
        'alias_match_failure'  — nflverse name could not be resolved
        'null_snap_pct'        — snap data missing after alias resolution
        'null_rz_data'         — red zone data missing
        'low_completeness'     — player_features.completeness_score < threshold
        'prediction_skipped'   — prediction not generated (data insufficient)
    """

    __tablename__ = "data_quality_events"
    __table_args__ = (
        Index("ix_dq_events_season_week", "season", "week"),
        Index("ix_dq_events_unresolved", "resolved_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Nullable — not every event is tied to a specific player or game
    player_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="SET NULL"), index=True
    )
    game_id: Mapped[Optional[str]] = mapped_column(
        String(30), ForeignKey("games.game_id", ondelete="SET NULL")
    )

    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    auto_resolvable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<DataQualityEvent {self.event_type} S{self.season}W{self.week} "
            f"player={self.player_id}>"
        )
