from pydantic import BaseModel, ConfigDict
from decimal import Decimal
from datetime import datetime


class PredictionBase(BaseModel):
    player_id: str
    season_year: int
    week: int
    td_likelihood: Decimal
    model_odds: Decimal
    favor: int


class PredictionCreate(PredictionBase):
    pass


class PredictionResponse(PredictionBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionWithPlayer(BaseModel):
    player_id: str
    player_name: str
    team_name: str | None
    position: str | None
    headshot_url: str | None
    td_likelihood: float
    model_odds: str  # Formatted as "+250" or "-150"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
