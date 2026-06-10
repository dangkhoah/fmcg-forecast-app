from datetime import datetime
from pydantic import BaseModel


class DatasetResponse(BaseModel):
    id: str
    filename: str
    row_count: int | None
    columns_json: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetPreview(BaseModel):
    columns: list[str]
    rows: list[list]
    total_rows: int
