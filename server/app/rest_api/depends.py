from fastapi import Depends

from app.core.repository.repositories import RedisRepository, Repositories
from app.database import DatabaseDriver, get_db_driver


def get_repository(db_driver: DatabaseDriver = Depends(get_db_driver)) -> Repositories:
    """Dependency to get the repository instance"""
    return RedisRepository(db_driver)
