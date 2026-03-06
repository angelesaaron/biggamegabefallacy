# Import all models so that:
# 1. SQLAlchemy relationship() forward references resolve correctly.
# 2. Alembic autogenerate sees all tables when it imports this module.
from app.models.player import Player
from app.models.player_alias import PlayerAlias
from app.models.game import Game
from app.models.player_game_log import PlayerGameLog
from app.models.team_game_stats import TeamGameStats
from app.models.player_features import PlayerFeatures
from app.models.player_season_state import PlayerSeasonState
from app.models.prediction import Prediction
from app.models.sportsbook_odds import SportsbookOdds
from app.models.data_quality_event import DataQualityEvent
from app.models.rookie_bucket import RookieBucket

__all__ = [
    "Player",
    "PlayerAlias",
    "Game",
    "PlayerGameLog",
    "TeamGameStats",
    "PlayerFeatures",
    "PlayerSeasonState",
    "Prediction",
    "SportsbookOdds",
    "DataQualityEvent",
    "RookieBucket",
]
