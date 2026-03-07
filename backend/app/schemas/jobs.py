import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class JobCreate(BaseModel):
    domain_id: int
    dataset_id: int | None = None
    row_count: int = Field(default=1000, ge=1, le=1_000_000)
    parameters: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    id: int
    user_id: int
    domain_id: int
    dataset_id: int | None
    row_count: int
    parameters: dict[str, Any]
    status: str
    rq_job_id: str | None
    result_path: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("parameters", mode="before")
    @classmethod
    def parse_parameters(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v
