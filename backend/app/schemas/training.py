from datetime import datetime
from pydantic import BaseModel


class TrainingHistoryResponse(BaseModel):
    id: str
    dataset_id: str
    dataset_name: str
    dataset_row_count: int | None = None
    model_name: str
    model_key: str | None = None
    hyper_params_json: str = "{}"
    mape: float | None = None
    training_time: float | None = None
    status: str = "completed"
    created_at: datetime

    model_config = {"from_attributes": True}


class TrainingSaveRequest(BaseModel):
    dataset_id: str
    dataset_name: str
    dataset_row_count: int | None = None
    model_name: str
    model_key: str | None = None
    model_key: str | None = None
    hyper_params: dict = {}
    mape: float | None = None
    training_time: float | None = None
    status: str = "completed"
