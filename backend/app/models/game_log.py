from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index, func
from app.database import Base


class GameLog(Base):
    """Player game log - stores historical performance data"""
    __tablename__ = "game_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String(50), ForeignKey("players.player_id"), nullable=False, index=True)
    game_id = Column(String(50), nullable=False)  # Format: YYYYMMDD_AWAY@HOME
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)

    # Team info
    team = Column(String(10))
    team_id = Column(String(50))

    # Receiving stats
    receptions = Column(Integer, default=0)
    receiving_yards = Column(Integer, default=0)
    receiving_touchdowns = Column(Integer, default=0)
    targets = Column(Integer, default=0)
    long_reception = Column(Integer)
    yards_per_reception = Column(Numeric(5, 2))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    __table_args__ = (
        # Unique constraint: one game log per player per game
        Index('ix_game_logs_player_game', 'player_id', 'game_id', unique=True),
        # Index for querying by player and season
        Index('ix_game_logs_player_season_week', 'player_id', 'season_year', 'week'),
    )

    def __repr__(self):
        return f"<GameLog {self.player_id} {self.game_id} - {self.receptions} rec, {self.receiving_touchdowns} TD>"
