import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal
from app.models import ForecastEngine, HAS_XGB, HAS_LGB, HAS_PROPHET

logger = logging.getLogger(__name__)

router = APIRouter()


class TrainRequest(BaseModel):
    model_name: str
    hyper_params: Dict[str, Any] = Field(default_factory=dict)
    model_save_name: Optional[str] = None
    file_path: str = ""
    seasonality_period: int = 52
    date_format: Optional[str] = None


AVAILABLE = ["ExtraTrees", "RandomForest"]
if HAS_XGB:
    AVAILABLE.append("XGBoost")
if HAS_LGB:
    AVAILABLE.append("LightGBM")
if HAS_PROPHET:
    AVAILABLE.append("Prophet")
AVAILABLE.append("SVM")


@router.get("/available-models")
async def get_models():
    return {"models": AVAILABLE}


def emit(phase: str, progress: int, **extra):
    return f"data: {json.dumps({'phase': phase, 'progress': progress, **extra})}\n\n"


async def train_generator(req: TrainRequest):
    engine = ForecastEngine()
    engine.best_model_name = req.model_name
    engine.hyper_params = req.hyper_params
    if req.model_save_name:
        engine.best_model_name = req.model_save_name

    if not req.file_path:
        yield emit("error", 0, message="No dataset file path provided")
        return

    start_time = time.time()

    yield emit("preparing", 5, message="Preparing training data...")
    await asyncio.sleep(0)

    try:
        yield emit("training", 30, message="Training model...")
        await asyncio.sleep(0)

        is_trained, _ = engine.train(
            file_path=req.file_path,
            date_format=req.date_format,
            seasonality_period=req.seasonality_period,
            force_retrain=True,
        )
    except Exception as e:
        logger.error(f"Training failed: {e}")
        yield emit("error", 0, message=str(e))
        return

    yield emit("calculating_mape", 70, message="Calculating accuracy (MAPE)...")
    await asyncio.sleep(0)

    yield emit("persisting", 90, message="Persisting trained model...")
    await asyncio.sleep(0)

    dataset_name = os.path.splitext(os.path.basename(req.file_path))[0] if req.file_path else "unknown"
    model_key = f"{req.model_name}_{dataset_name}"
    engine.persist_model(model_key=model_key)

    elapsed = round(time.time() - start_time, 2)

    result = {
        "done": True,
        "progress": 100,
        "phase": "complete",
        "mape": engine.mape,
        "model_name": engine.best_model_name,
        "final_score": engine.mape,
        "training_time": elapsed,
        "model_key": model_key,
    }
    yield f"data: {json.dumps(result)}\n\n"


@router.post("/train")
async def start_training(request: TrainRequest):
    return StreamingResponse(train_generator(request), media_type="text/event-stream")
