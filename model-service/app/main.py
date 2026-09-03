import pandas as pd
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
from app.models import ForecastEngine, memory
from app.routers import train

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

app.include_router(train.router)

#  initializes a ForecastEngine. This is a custom object (defined in D:\Apps\fmcg-forecast-app\model-service\app\models.py) that contains all the complex math and logic needed to predict future sales.
engine = ForecastEngine() # lives for the entire duration of the application


class PredictRequest(BaseModel):
    file_path: str
    forecast_periods: int = 12
    seasonality_period: int = 12
    confidence_level: float = 0.95
    model_type: str = "ExtraTrees"
    aggregation: Literal["mean", "sum"] | None = "mean"
    frequency: str | None = None
    force_retrain: bool = False
    date_format: str | None = None
    original_filename: str | None = None
    trained_model_key: str | None = None


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
    model_type: str | None = None


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
        start_time = time.time()
        
        if payload.trained_model_key and not payload.force_retrain:
            loaded = engine.load_trained_model(payload.trained_model_key)
            if loaded:
                model_type_from_key = payload.trained_model_key.split("_")[0]
                logger.info(f"Using trained model '{payload.trained_model_key}' for prediction (model_type={model_type_from_key})")
                # Load the data to set max_date and product_outlet_map
                # Save feature_columns before _prepare_training_data overwrites them
                saved_feature_columns = engine.feature_columns
                engine._prepare_training_data(resolved_path, date_format=payload.date_format, seasonality_period=payload.seasonality_period)
                # Restore original feature columns so reindex matches the loaded model's training features
                engine.feature_columns = saved_feature_columns
                future = engine._generate_future_records(payload.forecast_periods, seasonality_period=payload.seasonality_period)
                if future.empty:
                    result_data = {"dates": [], "values": [], "detailed_records": []}
                else:
                    X_future = future.reindex(columns=engine.feature_columns, fill_value=0)
                    predictions = engine.model.predict(X_future)
                    future['sales_prediction'] = predictions
                    lower_bounds, upper_bounds = engine._calculate_intervals(X_future, payload.confidence_level)
                    future['lower'] = lower_bounds if lower_bounds is not None else predictions
                    future['upper'] = upper_bounds if upper_bounds is not None else predictions
                    records = []
                    for _, row in future.iterrows():
                        records.append({
                            "date": row["date"].strftime("%Y-%m-%d"),
                            "product_id": int(row.get("product_identifier", 0)) if pd.notnull(row.get("product_identifier", 0)) else 0,
                            "outlet_id": int(row.get("outlet", 0)) if pd.notnull(row.get("outlet", 0)) else 0,
                            "prediction": round(float(row.get("sales_prediction", 0)), 2)
                        })
                    agg = "sum" if payload.aggregation == "sum" else "mean"
                    group = future.groupby("date")["sales_prediction"]
                    group_l = future.groupby("date")["lower"]
                    group_u = future.groupby("date")["upper"]
                    chart = group.sum().reset_index() if agg == "sum" else group.mean().reset_index()
                    chart["lower"] = group_l.sum().values if agg == "sum" else group_l.mean().values
                    chart["upper"] = group_u.sum().values if agg == "sum" else group_u.mean().values
                    chart["date_str"] = chart["date"].dt.strftime("%Y-%m-%d")
                    result_data = {
                        "dates": chart["date_str"].tolist(),
                        "values": chart["sales_prediction"].round(2).tolist(),
                        "lower_bound": chart["lower"].round(2).tolist(),
                        "upper_bound": chart["upper"].round(2).tolist(),
                        "detailed_records": records,
                        "cached": True,
                        "detected_freq": "W" if getattr(engine, "detected_freq", "W-MON").startswith("W") else getattr(engine, "detected_freq", "W-MON"),
                        "training_time": round(time.time() - start_time,1),
                        "mape": engine.mape,
                        "model_type": model_type_from_key,
                    }
                return PredictResponse(**result_data)
        else:
            model_type_from_key = payload.model_type

        result = engine.predict(
            file_path=resolved_path,
            forecast_periods=payload.forecast_periods,
            seasonality_period=payload.seasonality_period,
            confidence_level=payload.confidence_level,
            aggregation=payload.aggregation,
            model_type=model_type_from_key,
            force_retrain=payload.force_retrain,
            frequency=payload.frequency,
            date_format=payload.date_format,
        )
        # logger.info(f"Prediction successful: {result}") # very long result, so we log it at debug level instead
        logger.info(f"Prediction successful for {filename}. Model: {result.get('model_type')}, MAPE: {result.get('mape')}")
        logger.debug(f"Detailed result: {result}")
    except Exception as e:
        logger.error(f"Prediction failed for {payload.file_path}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    return PredictResponse(**result)


@app.get("/trained-models")
async def get_trained_models():
    return {"models": ForecastEngine.list_trained_models()}


@app.get("/trained-models/{model_key}/metadata")
async def get_trained_model_metadata(model_key: str):
    meta = ForecastEngine.load_trained_model_metadata(model_key)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Trained model '{model_key}' not found")
    return meta
