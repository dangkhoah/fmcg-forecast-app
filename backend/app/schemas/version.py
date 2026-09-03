from datetime import datetime
from pydantic import BaseModel


class VersionSaveRequest(BaseModel):
    forecast_id: str
    dataset_id: str
    dataset_name: str
    version_label: str
    notes: str | None = None
    parameters: dict = {}
    result: dict = {}


class VersionResponse(BaseModel):
    id: str
    forecast_id: str
    dataset_id: str
    dataset_name: str
    version_label: str
    notes: str | None = None
    parameters_json: str
    result_json: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ComparisonPoint(BaseModel):
    date: str
    values: dict[str, float | None]


class ComparisonResponse(BaseModel):
    versions: list[VersionResponse]
    comparison_data: list[ComparisonPoint]
