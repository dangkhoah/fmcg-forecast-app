from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from sklearn.ensemble import ExtraTreesRegressor
from app.models import ForecastEngine, memory

from pathlib import Path
import logging
from contextlib import asynccontextmanager

# Configure logging to write to a file. In production, you might want to use a more robust logging configuration --> already used in D:\Apps\fmcg-forecast-app\model-service\logging.ini
# logging.basicConfig(
#     filename='model_service.log',
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    cache_dir = Path(__file__).resolve().parent.parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    logger.info(f"♻️ Initialized persistent cache at {cache_dir}")
    engine.load_reference_data()
    logger.info(f"engine.cached (default): {engine.cached} ✅")
    yield
    # Shutdown logic (if any) can go here

app = FastAPI(title="FMCG Forecast Model Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
#  initializes a ForecastEngine. This is a custom object (defined in D:\Apps\fmcg-forecast-app\model-service\app\models.py) that contains all the complex math and logic needed to predict future sales.
engine = ForecastEngine() # lives for the entire duration of the application


class PredictRequest(BaseModel):
    file_path: str
    forecast_periods: int = 12
    seasonality_period: int = 12
    confidence_level: float = 0.95
    model_type: Literal["ExtraTrees", "MovingAverage"] = "ExtraTrees"
    aggregation: Literal["mean", "sum"] | None = "mean"
    frequency: str | None = None
    force_retrain: bool = False
    date_format: str | None = None
    original_filename: str | None = None  # Optional field to specify the original filename of the dataset


class PredictResponse(BaseModel):
    dates: list[str]
    values: list[float]
    lower_bound: list[float] | None = None
    upper_bound: list[float] | None = None
    detailed_records: list[dict] | None = None
    cached: bool = False
    training_time: float = 0.0
    detected_freq: str | None = None
    mape: float | None = None


@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": engine.model is not None}


@app.post("/clear-cache")
async def clear_cache():
    logger.info("Received request to clear model cache.")
    memory.clear()
    logger.info("Model cache cleared successfully.")
    return {"status": "ok", "message": "Cache cleared."}


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    try:
        # Always resolve the dataset file in the current backend/uploads directory.
        # The DB may store absolute paths from a previous machine, so we extract
        # just the filename and look it up in the known uploads location.
        uploads_dir = Path(__file__).resolve().parents[2] / "backend" / "uploads"
        # Use the original filename if provided, otherwise fall back to extracting from path
        filename = Path(payload.file_path).name # extract just the filename uploaded by the user
        logger.info(f"Received prediction request for: {payload.original_filename}/{filename}")
        logger.info(f"Received prediction request (payload): {payload.model_dump_json()}")
        resolved_path = str(uploads_dir / filename)
        logger.info(f"File path from payload: {payload.file_path}")
        logger.info(f"Resolved dataset path: {resolved_path}")
        
        # engine.model = ExtraTreesRegressor(n_estimators=100, max_features=None, verbose=0, n_jobs=-1) if payload.model_type == "ExtraTrees" else None
        result = engine.predict(
            file_path=resolved_path,
            forecast_periods=payload.forecast_periods,
            seasonality_period=payload.seasonality_period,
            confidence_level=payload.confidence_level,
            aggregation=payload.aggregation,
            model_type=payload.model_type,
            force_retrain=payload.force_retrain,
            frequency=payload.frequency,
            date_format=payload.date_format,
        )
        # logger.info(f"Prediction successful: {result}") # very long result, so we log it at debug level instead
        logger.info(f"Prediction successful for {filename}. MAPE: {result.get('mape')}")
        logger.debug(f"Detailed result: {result}")
    except Exception as e:
        logger.error(f"Prediction failed for {payload.file_path}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return PredictResponse(**result)
