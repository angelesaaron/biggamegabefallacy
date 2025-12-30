from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "BGGTDM API"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/bggtdm"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # API Keys
    RAPIDAPI_KEY: str = ""  # Legacy - no longer used
    ODDS_API_KEY: str = ""   # Legacy - no longer used
    TANK01_API_KEY: str = "" # Tank01 NFL API (primary data source)

    # Model
    MODEL_PATH: str = "models/wr-model.pkl"

    # NFL Season Config
    NFL_SEASON_YEAR: int = 2025
    NFL_CURRENT_WEEK: int = 1

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
