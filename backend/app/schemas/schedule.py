from datetime import datetime
from pydantic import BaseModel


class ScheduleConfigCreate(BaseModel):
    name: str
    dataset_id: str
    dataset_name: str
    models: list[str]
    hyper_params: dict = {}
    seasonality_period: int = 52
    date_format: str | None = None
    schedule_type: str = "daily"
    day_of_week: int | None = None
    day_of_month: int | None = None
    hour: int = 0
    minute: int = 0


class ScheduleConfigUpdate(BaseModel):
    name: str | None = None
    models: list[str] | None = None
    hyper_params: dict | None = None
    seasonality_period: int | None = None
    date_format: str | None = None
    schedule_type: str | None = None
    day_of_week: int | None = None
    day_of_month: int | None = None
    hour: int | None = None
    minute: int | None = None
    is_active: bool | None = None


class ScheduleConfigResponse(BaseModel):
    id: str
    name: str
    dataset_id: str
    dataset_name: str
    models_json: str
    hyper_params_json: str
    seasonality_period: int
    date_format: str | None = None
    schedule_type: str
    day_of_week: int | None = None
    day_of_month: int | None = None
    hour: int
    minute: int
    is_active: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
