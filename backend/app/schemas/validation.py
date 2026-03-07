import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class ColumnScore(BaseModel):
    column: str
    score: float
    ks: float


class ValidationReportResponse(BaseModel):
    id: int
    job_id: int
    status: str
    overall_score: float | None
    ks_statistic: float | None
    correlation_delta: float | None
    coverage_score: float | None
    column_scores: list[ColumnScore]
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("column_scores", mode="before")
    @classmethod
    def parse_column_scores(cls, v: Any) -> Any:
        if isinstance(v, str):
            return json.loads(v)
        return v
