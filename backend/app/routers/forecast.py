import json
import os
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.forecast import ForecastResult, ForecastScenario
from app.schemas.forecast import ForecastRequest, ForecastResponse, ScenarioCreate, ScenarioResponse
from app.services.auth import get_current_user
from app.services.forecast_client import call_forecast_model, get_client
from app.config import settings

logger = logging.getLogger(__name__)
# Prefix is now handled by the inclusion in main.py (D:\Apps\fmcg-forecast-app\backend\app\main.py), making this more portable
# Change from prefix="/api/forecast" to:
router = APIRouter(prefix="/forecast", tags=["forecast"])

@router.post("/clear-cache")
async def clear_model_cache(current_user: User = Depends(get_current_user)):
    """
    Proxies the request to clear the cache on the model service.
    """
    client = get_client()
    clear_cache_url = str(settings.FORECAST_API_URL).replace("/predict", "/clear-cache")
    try:
        resp = await client.post(clear_cache_url, timeout=30.0)
        resp.raise_for_status()
        logger.info(f"User {current_user.id} cleared the model service cache.")
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to clear model cache: {str(e)}")

@router.post("/", response_model=ForecastResponse)
async def run_forecast(
    payload: ForecastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == payload.dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # The DB may store absolute paths from a previous machine.
    # Resolve to the current uploads directory using just the filename.
    stored_path = dataset.file_path
    actual_path = os.path.join(settings.UPLOAD_DIR, os.path.basename(stored_path))

    model_input = {
        "file_path": actual_path,
        "forecast_periods": payload.forecast_periods,
        "seasonality_period": payload.seasonality_period,
        "confidence_level": payload.confidence_level,
        "model_type": payload.model_type,
        "frequency": payload.frequency,
        "force_retrain": payload.force_retrain,
        "aggregation": payload.aggregation, # already included in additional_params if provided
        "date_format": payload.date_format,
        "original_filename": dataset.filename, # Pass the original filename
        **(payload.additional_params or {}),
    }

    try:
        model_result = await call_forecast_model(model_input)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forecast model error: {str(e)}")

    # Performance monitoring log
    training_time = model_result.get("training_time", 0)
    is_cached = model_result.get("cached", False)
    logger.info(
        f"FORECAST_PERFORMANCE: dataset_id={dataset.id} rows={dataset.row_count} "
        f"duration={training_time}s cached={is_cached} user_id={current_user.id}"
    )

    forecast = ForecastResult(
        user_id=current_user.id,
        dataset_id=payload.dataset_id,
        parameters_json=payload.model_dump_json(), # Serialize the request parameters for record-keeping
        result_json=json.dumps(model_result),
    )
    db.add(forecast)
    await db.commit()
    await db.refresh(forecast)

    # Dynamic mapping: Merge DB info with all fields returned by the model service
    response_data = {
        "id": forecast.id,
        "name": getattr(forecast, "name", None),
        "dataset_id": payload.dataset_id,
        "dataset_name": dataset.filename,
        "dataset_row_count": dataset.row_count,
        "created_at": forecast.created_at,
        "parameters": payload.model_dump(),
        **model_result
    }

    return ForecastResponse(**response_data)


@router.post("/scenarios", response_model=ScenarioResponse)
async def create_scenario(
    payload: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == payload.dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    actual_path = os.path.join(settings.UPLOAD_DIR, os.path.basename(dataset.file_path))
    model_input = {"file_path": actual_path, **payload.parameters}
    try:
        model_result = await call_forecast_model(model_input)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forecast model error: {str(e)}")

    scenario = ForecastScenario(
        user_id=current_user.id,
        dataset_id=payload.dataset_id,
        name=payload.name,
        parameters_json=json.dumps(payload.parameters),
        result_json=json.dumps(model_result),
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    return scenario


@router.get("/scenarios", response_model=list[ScenarioResponse])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ForecastScenario)
        .where(ForecastScenario.user_id == current_user.id)
        .order_by(ForecastScenario.created_at.desc())
    )
    return result.scalars().all()


@router.get("/history", response_model=list[ForecastResponse])
async def forecast_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ForecastResult, Dataset.id, Dataset.filename, Dataset.row_count)
        .join(Dataset, ForecastResult.dataset_id == Dataset.id)
        .where(ForecastResult.user_id == current_user.id)
        .order_by(ForecastResult.created_at.desc())
    )
    # Fetch all columns from the join
    forecasts = result.all() 
    responses = []
    for f, dataset_id, filename, row_count in forecasts:
        r = json.loads(f.result_json)
        p = json.loads(f.parameters_json) if f.parameters_json else {}
        
        # Dynamic unpacking for history
        hist_data = {
            "id": f.id,
            "name": getattr(f, "name", None),
            "dataset_id": dataset_id,
            "dataset_name": filename,
            "dataset_row_count": row_count,
            "created_at": f.created_at,
            "parameters": p,
            **r
        }
            
        responses.append(ForecastResponse(**hist_data))
    return responses

@router.delete("/history/clear")
async def clear_forecast_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deletes all forecast results for the current user.
    """
    await db.execute(
        delete(ForecastResult).where(ForecastResult.user_id == current_user.id)
    )
    await db.commit()
    return {"detail": "All forecast history cleared"}

@router.patch("/{forecast_id}", response_model=ForecastResponse)
async def rename_forecast(
    forecast_id: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # We join with Dataset to get the filename required by ForecastResponse
    result = await db.execute(
        select(ForecastResult, Dataset.id, Dataset.filename, Dataset.row_count)
        .join(Dataset, ForecastResult.dataset_id == Dataset.id)
        .where(ForecastResult.id == forecast_id, ForecastResult.user_id == current_user.id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Forecast not found")

    forecast, dataset_id, filename, row_count = row
    forecast.name = name
    await db.commit()
    await db.refresh(forecast)

    # Manually construct the response to satisfy the schema requirements
    r = json.loads(forecast.result_json)
    rename_data = {
        "id": forecast.id,
        "name": forecast.name,
        "dataset_id": dataset_id,
        "dataset_name": filename,
        "dataset_row_count": row_count,
        "created_at": forecast.created_at,
        "parameters": json.loads(forecast.parameters_json) if forecast.parameters_json else {},
        **r
    }

    return ForecastResponse(**rename_data)


@router.delete("/{forecast_id}")
async def delete_forecast(
    forecast_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ForecastResult).where(ForecastResult.id == forecast_id, ForecastResult.user_id == current_user.id)
    )
    forecast = result.scalar_one_or_none()
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    await db.delete(forecast)
    await db.commit()
    return {"detail": "Forecast deleted"}
@router.get("/policy")
async def get_interaction_policy():
    """
    Reads the .cursorrules file from the project root and returns it.
    """
    # Resolve path to the project root .cursorrules
    # Path(__file__) is in backend/app/routers/, so we go up 3 levels to reach fmcg-forecast-app/
    policy_path = Path(__file__).resolve().parents[3] / ".cursorrules"
    
    if not policy_path.exists():
        raise HTTPException(status_code=404, detail="Policy file (.cursorrules) not found at project root")
    
    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading policy file: {str(e)}")
