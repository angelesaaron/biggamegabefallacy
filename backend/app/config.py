from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os


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
    @property
    def MODEL_PATH(self) -> str:
        """
        Get model path with fallback logic for different environments.

        Checks in order:
        1. MODEL_PATH environment variable
        2. /app/models/wr-model.pkl (Docker/production)
        3. ../models/wr-model.pkl (relative to backend dir, dev)
        4. ../../models/wr-model.pkl (relative to app dir, dev)
        """
        # Check environment variable first
        env_path = os.getenv("MODEL_PATH")
        if env_path:
            return env_path

        # Try production path (Docker)
        prod_path = Path("/app/models/wr-model.pkl")
        if prod_path.exists():
            return str(prod_path)

        # Try development paths
        config_file = Path(__file__)

        # From backend/app/config.py -> models/wr-model.pkl
        dev_path1 = config_file.parent.parent / "models" / "wr-model.pkl"
        if dev_path1.exists():
            return str(dev_path1)

        # From backend/app/config.py -> ../../models/wr-model.pkl (project root)
        dev_path2 = config_file.parent.parent.parent / "models" / "wr-model.pkl"
        if dev_path2.exists():
            return str(dev_path2)

        # Fallback to relative path
        return "models/wr-model.pkl"

    # NFL Season Config
    NFL_SEASON_YEAR: int = 2025
    NFL_CURRENT_WEEK: int = 1

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
