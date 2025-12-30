from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class PlayerBase(BaseModel):
    player_id: str
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    position: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    age: Optional[int] = None
    experience_years: Optional[int] = None
    active_status: bool = True
    headshot_url: Optional[str] = None


class PlayerCreate(PlayerBase):
    pass


class PlayerResponse(PlayerBase):
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PlayerListItem(BaseModel):
    player_id: str
    full_name: str
    team_name: Optional[str] = None
    position: Optional[str] = None
    headshot_url: Optional[str] = None
    active_status: bool = True

    model_config = ConfigDict(from_attributes=True)
