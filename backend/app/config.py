import os
from pathlib import Path
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/fmcg_forecast"
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    FORECAST_API_URL: str = "http://localhost:8001/predict"
    MODEL_SERVICE_URL: str = "http://localhost:8001"
    UPLOAD_DIR: str = str(ROOT_DIR / "uploads")
    MODEL_SERVICE_TIMEOUT: int = 120
    LOG_SQL: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
