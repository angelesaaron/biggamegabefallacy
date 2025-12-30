from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime


class SportsbookOddsBase(BaseModel):
    player_id: str
    season_year: int
    week: int
    sportsbook: str
    odds: Decimal


class SportsbookOddsCreate(SportsbookOddsBase):
    pass


class SportsbookOddsResponse(SportsbookOddsBase):
    id: int
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OddsComparison(BaseModel):
    player_id: str
    player_name: str
    team_name: str | None
    model_odds: str
    sportsbook_odds: dict[str, str]  # {"DraftKings": "+220", "FanDuel": "+200"}
    best_book: str | None
    best_edge: int | None

    model_config = ConfigDict(from_attributes=True)
