from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PlayerAlias(Base):
    """
    Maps external source names to canonical Tank01 player_ids.

    This table is the fix for silent NaN failures from name-matching across
    data sources (nflverse, sleeper, ESPN). Every external join goes through
    this table — zero guessing at runtime. Failed matches emit a
    data_quality_event, never a silent NULL in a feature row.

    Built once during backfill, maintained by the data quality pipeline
    when new match failures appear.
    """

    __tablename__ = "player_aliases"
    __table_args__ = (
        UniqueConstraint("player_id", "source", name="uq_player_alias_player_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # 'nflverse', 'sleeper', 'espn'
    alias_name: Mapped[str] = mapped_column(String(150), nullable=False)
    match_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'exact', 'manual', 'fuzzy'
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="aliases")

    def __repr__(self) -> str:
        return f"<PlayerAlias {self.source}:{self.alias_name} → {self.player_id}>"
