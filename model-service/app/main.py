from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal

from app.models import ForecastEngine

from pathlib import Path
import logging

# Configure logging to write to a file. In production, you might want to use a more robust logging configuration --> already used in D:\Apps\fmcg-forecast-app\model-service\logging.ini
# logging.basicConfig(
#     filename='model_service.log',
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger(__name__)

app = FastAPI(title="FMCG Forecast Model Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ForecastEngine()


class PredictRequest(BaseModel):
    file_path: str
    forecast_periods: int = 12
    seasonality_period: int = 12
    confidence_level: float = 0.95
    aggregation: Literal["mean", "sum"] | None = "mean"


class PredictResponse(BaseModel):
    dates: list[str]
    values: list[float]
    lower_bound: list[float] | None = None
    upper_bound: list[float] | None = None
    records: list[dict] | None = None
    cached: bool = False
    training_time: float = 0.0
    mape: float | None = None


@app.on_event("startup")
async def startup():
    engine.load_reference_data()


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": engine.model is not None}


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    try:
        logger.info(f"Received prediction request: {payload.json()}")
        # Always resolve the dataset file in the current backend/uploads directory.
        # The DB may store absolute paths from a previous machine, so we extract
        # just the filename and look it up in the known uploads location.
        uploads_dir = Path(__file__).resolve().parents[2] / "backend" / "uploads"
        filename = Path(payload.file_path).name  # extract just the filename
        resolved_path = str(uploads_dir / filename)
        logger.info(f"Original file_path: {payload.file_path}")
        logger.info(f"Resolved dataset path: {resolved_path}")
        result = engine.predict(
            file_path=resolved_path,
            forecast_periods=payload.forecast_periods,
            seasonality_period=payload.seasonality_period,
            confidence_level=payload.confidence_level,
            aggregation=payload.aggregation,
        )
        logger.info(f"Prediction successful: {result}")
    except Exception as e:
        logger.error(f"Prediction failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return PredictResponse(**result)
