from datetime import datetime
from pydantic import BaseModel


class ForecastRequest(BaseModel):
    dataset_id: str
    forecast_periods: int = 12
    seasonality_period: int = 12
    confidence_level: float = 0.95
    model_type: str = "ExtraTrees"
    frequency: str | None = None
    force_retrain: bool = False
    aggregation: str | None = None
    date_format: str | None = None
    original_filename: str | None = None # Add this line
    additional_params: dict | None = None


class ForecastResponse(BaseModel):
    id: str
    name: str | None = None
    dataset_id: str | None = None
    dataset_name: str | None = None
    dataset_row_count: int | None = None
    dates: list[str]
    values: list[float]
    lower_bound: list[float] | None = None
    upper_bound: list[float] | None = None
    detailed_records: list[dict] | None = None
    created_at: datetime
    parameters: dict | None = None
    cached: bool = False
    training_time: float | None = None
    detected_freq: str | None = None
    mape: float | None = None


class ScenarioCreate(BaseModel):
    dataset_id: str
    name: str
    parameters: dict


class ScenarioResponse(BaseModel):
    id: str
    name: str
    parameters_json: str
    result_json: str
    created_at: datetime

    model_config = {"from_attributes": True}
