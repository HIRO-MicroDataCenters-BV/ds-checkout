from typing import Any, AsyncGenerator, Dict

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import setup_logging

from .database import RedisDatabase
from .rest_api.routes import health_check, orders
from .settings import get_settings

settings = get_settings()
db = RedisDatabase(
    protocol=settings.database.protocol,
    host=settings.database.host,
    port=settings.database.port,
    db_number=settings.database.db_number,
    username=settings.database.username,
    password=settings.database.password,
)


class CustomFastAPI(FastAPI):
    def openapi(self) -> Dict[str, Any]:
        if self.openapi_schema:
            return self.openapi_schema
        openapi_schema = get_openapi(
            title="Checkout service",
            version="0.0.0",
            description="This is a checkout service for temporary storage of orders",
            contact={
                "name": "HIRO-MicroDataCenters",
                "email": "all-hiro@hiro-microdatacenters.nl",
            },
            license_info={
                "name": "MIT",
                "url": "https://github.com/HIRO-MicroDataCenters-BV"
                "/template-python/blob/main/LICENSE",
            },
            routes=self.routes,
        )
        self.openapi_schema = openapi_schema
        return self.openapi_schema


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await db.connect()
    yield
    await db.close()


app = CustomFastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(health_check.routes.router)
app.include_router(orders.routes.router)
