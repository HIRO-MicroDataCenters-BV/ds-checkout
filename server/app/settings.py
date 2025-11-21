from typing import Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    protocol: str = "redis"
    host: str = "localhost"
    port: int = 6379
    db_number: int = 0  # Default Redis DB 0
    username: Optional[str] = None
    password: Optional[str] = None


class Settings(BaseSettings):
    ORDER_TTL_SECONDS: int = 7200  # 120 minutes
    ORDER_KEY_PREFIX: str = "order:"  # Prefix for order keys in storage
    ORDER_TTL_ENABLED: bool = True
    MAX_PAYLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # URL mapping configuration
    DS_CONNECTOR_BASE_URL: str = (
        "https://ds-connector.{region}.nextgen.hiro-develop.nl/distribution-content"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    database: Database = Database()
    test_database: Database = Database(db_number=15)


def get_settings() -> Settings:
    settings = Settings()
    return settings
