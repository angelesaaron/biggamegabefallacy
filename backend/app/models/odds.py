from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index, func, UniqueConstraint
from app.database import Base


class SportsbookOdds(Base):
    """
    Stores sportsbook odds for player anytime TD props.

    Data fetched from Tank01 getNFLBettingOdds endpoint using gameID parameter.
    Stores DraftKings and FanDuel odds separately for comparison.
    """
    __tablename__ = "sportsbook_odds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String(50), ForeignKey("players.player_id"), nullable=False)
    game_id = Column(String(50), ForeignKey("schedule.game_id"), nullable=False)  # Links to specific game
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    sportsbook = Column(String(50), nullable=False, index=True)  # 'draftkings', 'fanduel'
    anytime_td_odds = Column(Integer, nullable=False)  # American odds (e.g., +175, -140)

    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('player_id', 'game_id', 'sportsbook', name='uix_odds_player_game_book'),
        Index('ix_odds_season_week', 'season_year', 'week'),
        Index('ix_odds_player_week', 'player_id', 'season_year', 'week'),
        Index('ix_odds_game', 'game_id'),
    )

    def __repr__(self):
        return f"<SportsbookOdds {self.sportsbook} {self.player_id} {self.game_id}>"
