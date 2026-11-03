from typing import Dict, Optional

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Database(BaseModel):
    protocol: str = "redis"
    host: str = "localhost"
    port: int = 6379
    db_number: int = 0  # Default Redis DB 0
    username: Optional[str] = None
    password: Optional[str] = None


class ContractGeneratorSettings(BaseModel):
    """One node's contract generator: where it is, and the node it signs for."""

    url: str
    # Must equal that generator's DS__NODE_ID: it refuses any item whose host
    # is not its node.
    node_id: str


class Settings(BaseSettings):
    ORDER_TTL_SECONDS: int = 7200  # 120 minutes
    ORDER_KEY_PREFIX: str = "order:"  # Prefix for order keys in storage
    ORDER_TTL_ENABLED: bool = True
    MAX_PAYLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # Contract issuing. After an order is stored, checkout asks each region's
    # contract generator for a contract covering that region's datasets.
    # Region (as on each dataset, e.g. "hus") -> generator, as JSON, e.g.
    #   {"hus": {"url": "http://ds-contract-generator.hus.svc.cluster.local:8082",
    #            "node_id": "hus.nextgen.hiro-develop.nl"}}
    # Empty: no contracts. Issuing never blocks an order (see core/contracts.py).
    CONTRACT_GENERATORS: Dict[str, ContractGeneratorSettings] = {}
    # Named as the consumer when the caller sends no ds-login token (Authorization:
    # Bearer). The token is read, not verified, until tokens are checked.
    CONTRACT_DEFAULT_CONSUMER_ID: str = "unknown@local"

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
