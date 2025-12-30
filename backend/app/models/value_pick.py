from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index, func, UniqueConstraint
from app.database import Base


class ValuePick(Base):
    __tablename__ = "value_picks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String(50), ForeignKey("players.player_id"), nullable=False)
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    sportsbook = Column(String(50), nullable=False, index=True)

    model_odds = Column(Numeric(8, 2), nullable=False)
    sportsbook_odds = Column(Numeric(8, 2), nullable=False)

    model_probability = Column(Numeric(10, 6))
    sportsbook_probability = Column(Numeric(10, 6))
    weighted_value = Column(Numeric(10, 6), index=True)  # For sorting by edge

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('player_id', 'season_year', 'week', 'sportsbook', name='uix_value_pick_unique'),
        Index('ix_value_picks_season_week_value', 'season_year', 'week', 'weighted_value'),
    )

    def __repr__(self):
        return f"<ValuePick {self.sportsbook} {self.player_id} W{self.week}>"
