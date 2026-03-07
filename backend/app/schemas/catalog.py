from datetime import datetime

from pydantic import BaseModel, Field


class DomainResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str

    model_config = {"from_attributes": True}


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="")
    domain_id: int
    storage_path: str = Field(min_length=1, max_length=500)
    row_count: int = Field(default=0, ge=0)
    column_count: int = Field(default=0, ge=0)
    credit_cost: int = Field(default=1, ge=0)


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: str
    domain_id: int
    domain: DomainResponse
    row_count: int
    column_count: int
    credit_cost: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetListItem(BaseModel):
    id: int
    name: str
    description: str
    domain: DomainResponse
    row_count: int
    column_count: int
    credit_cost: int
    status: str

    model_config = {"from_attributes": True}
