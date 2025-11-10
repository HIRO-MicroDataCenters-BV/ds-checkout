from pydantic import BaseModel, Field


class HealthCheck(BaseModel):
    status: str = Field(examples=["OK"])
