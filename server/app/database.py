from typing import Any, Optional

import redis.asyncio as redis

DatabaseDriver = Any  # Redis client type


class DatabaseError(Exception):
    ...


class DatabaseNotInitializedError(DatabaseError):
    def __init__(self, message="Database is not initialized"):
        self.message = message
        super().__init__(self.message)


class DriverNotInitializedError(DatabaseError):
    def __init__(self, message="Database driver is not initialized"):
        self.message = message
        super().__init__(self.message)


class RedisDatabase:
    _instance: Optional["RedisDatabase"] = None

    uri: str
    db_number: int
    auth: tuple[str, str]

    driver: Any = None  # Redis client

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        protocol: str,
        host: str,
        port: int,
        db_number: int,
        username: Optional[str],
        password: Optional[str],
    ):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.db_number = db_number
        self.username = username
        self.password = password
        self.uri = f"{protocol}://{host}:{port}"
        self.auth = (username or "", password or "")
        self.driver = None

    @classmethod
    def get_instance(cls) -> "RedisDatabase":
        if not cls._instance:
            raise DatabaseNotInitializedError()
        return cls._instance

    async def connect(self) -> Any:  # Returns Redis client
        if self.driver is None:
            self.driver = redis.Redis(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                decode_responses=True,
            )
        await self.driver.ping()
        return self.driver

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()


def get_db_driver() -> Any:  # Returns Redis client
    driver = RedisDatabase.get_instance().driver
    if not driver:
        raise DriverNotInitializedError()
    return driver
