from sqlalchemy import Column, String, Integer, Boolean, DateTime, Index, func
from app.database import Base


class Schedule(Base):
    """NFL game schedule - maps gameID to week number"""
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(50), nullable=False, unique=True, index=True)  # Format: YYYYMMDD_AWAY@HOME
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    season_type = Column(String(20), nullable=False)  # 'reg', 'pre', 'post'

    # Game details
    home_team = Column(String(10))
    away_team = Column(String(10))
    home_team_id = Column(String(50))
    away_team_id = Column(String(50))
    game_date = Column(String(20))  # YYYYMMDD format
    game_status = Column(String(20))  # 'Scheduled', 'InProgress', 'Final', etc.
    neutral_site = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    __table_args__ = (
        Index('ix_schedule_season_week', 'season_year', 'week'),
    )

    def __repr__(self):
        return f"<Schedule {self.game_id} - {self.season_year} Week {self.week}>"
