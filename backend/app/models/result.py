from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, Index, func, UniqueConstraint
from app.database import Base


class GameResult(Base):
    __tablename__ = "game_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String(50), ForeignKey("players.player_id"), nullable=False)
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)

    receiving_touchdowns = Column(Integer, nullable=False, default=0)
    receptions = Column(Integer)
    receiving_yards = Column(Integer)
    targets = Column(Integer)

    game_date = Column(Date)
    opponent_team_id = Column(String(50))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('player_id', 'season_year', 'week', name='uix_result_unique'),
        Index('ix_results_season_week', 'season_year', 'week'),
    )

    def __repr__(self):
        return f"<GameResult {self.player_id} W{self.week} {self.receiving_touchdowns} TDs>"
