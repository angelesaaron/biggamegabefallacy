from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index, func, UniqueConstraint
from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String(50), ForeignKey("players.player_id"), nullable=False)
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    td_likelihood = Column(Numeric(5, 4), nullable=False)  # 0.0000 to 1.0000
    model_odds = Column(Numeric(8, 2), nullable=False)
    favor = Column(Integer, nullable=False)  # 1 for underdog (+), -1 for favorite (-)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('player_id', 'season_year', 'week', name='uix_player_season_week'),
        Index('ix_predictions_season_week', 'season_year', 'week'),
    )

    def __repr__(self):
        return f"<Prediction {self.player_id} W{self.week} {self.model_odds}>"
