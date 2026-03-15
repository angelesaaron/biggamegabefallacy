from pathlib import Path
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "BGGTDM API v2"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/bggtdm_v2"

    # CORS — comma-separated in env, list in code
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",")]
        return v

    @model_validator(mode="after")
    def check_jwt_secret(self) -> "Settings":
        import os
        if not self.JWT_SECRET_KEY and os.environ.get("PYTEST_CURRENT_TEST") is None:
            raise ValueError(
                "JWT_SECRET_KEY must be set. Generate one with: openssl rand -hex 32"
            )
        return self

    # API Keys
    TANK01_API_KEY: str = ""
    ADMIN_KEY: str = ""  # Required for all /admin/* endpoints

    # JWT — generate JWT_SECRET_KEY with: openssl rand -hex 32
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ML Model
    MODEL_PATH: str = "../ml/model/wr_te_model_v2.pkl"
    MODEL_VERSION: str = "v2_xgb"

    # nflverse cache
    # nfl_data_py downloads ~300MB of PBP parquet files on first use.
    # On ephemeral hosting (e.g. Render free tier), this cache is wiped on each deploy.
    # First ingest after a cold deploy will re-download ~300MB.
    # For production, mount a persistent disk and point NFLVERSE_CACHE_DIR at it.
    NFLVERSE_CACHE_DIR: str = str(Path.home() / ".bggtdm_cache" / "nflverse")

    def resolved_model_path(self) -> Path:
        p = Path(self.MODEL_PATH)
        if p.is_absolute():
            return p
        return (Path(__file__).parent.parent / p).resolve()


settings = Settings()
