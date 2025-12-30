from sqlalchemy import Column, String, Integer, Boolean, DateTime, func
from app.database import Base


class Player(Base):
    __tablename__ = "players"

    player_id = Column(String(50), primary_key=True, index=True)
    full_name = Column(String(100), nullable=False, index=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    team_id = Column(String(50))
    team_name = Column(String(100))
    position = Column(String(10), index=True)
    jersey_number = Column(String(10))  # Tank01 field: jerseyNum
    height = Column(String(10))  # Tank01 returns as string like '6\'1"'
    weight = Column(String(10))  # Tank01 returns as string, sometimes 'R' for rookies
    age = Column(String(10))     # Tank01 returns as string, sometimes 'R' for rookies
    experience_years = Column(String(10))  # Tank01 returns as string, sometimes 'R' for rookies
    active_status = Column(Boolean, default=True, index=True)
    headshot_url = Column(String(500))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<Player {self.full_name} ({self.team_name})>"
