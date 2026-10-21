"""Application configuration using Pydantic Settings."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Warehouse Order Management System"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database URLs
    # If USE_SQLITE is true, aiosqlite is used as local engine
    USE_SQLITE: bool = True
    SQLITE_DB_PATH: str = "./warehouse_local.db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/warehouse_db"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/warehouse_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_FAKE_REDIS: bool = True
    CACHE_TTL_SECONDS: int = 300

    # Optimization
    DEFAULT_ROUTING_STRATEGY: str = "OR_TOOLS_LP"  # or NEAREST_GREEDY
    MAX_WAREHOUSE_SPLITS: int = 3

    # Fault Tolerance & Retries
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 0.05
    RETRY_MAX_DELAY: float = 1.0
    RETRY_JITTER: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIME: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def effective_async_db_url(self) -> str:
        if self.USE_SQLITE:
            return f"sqlite+aiosqlite:///{self.SQLITE_DB_PATH}"
        return self.DATABASE_URL


settings = Settings()
