import json
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.models.forecast import ForecastResult, ForecastScenario
from app.schemas.forecast import ForecastRequest, ForecastResponse, ScenarioCreate, ScenarioResponse
from app.services.auth import get_current_user
from app.services.forecast_client import call_forecast_model
from app.config import settings

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


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
        **(payload.additional_params or {}),
    }

    try:
        model_result = await call_forecast_model(model_input)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forecast model error: {str(e)}")

    forecast = ForecastResult(
        user_id=current_user.id,
        dataset_id=payload.dataset_id,
        parameters_json=payload.model_dump_json(), # Serialize the request parameters for record-keeping
        result_json=json.dumps(model_result),
    )
    db.add(forecast)
    await db.commit()
    await db.refresh(forecast)

    return ForecastResponse(
        id=forecast.id,
        dates=model_result.get("dates", []),
        values=model_result.get("values", []),
        lower_bound=model_result.get("lower_bound"),
        upper_bound=model_result.get("upper_bound"),
        detailed_records=model_result.get("records"),
        created_at=forecast.created_at,
    )


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
        select(ForecastResult)
        .where(ForecastResult.user_id == current_user.id)
        .order_by(ForecastResult.created_at.desc())
    )
    forecasts = result.scalars().all()
    responses = []
    for f in forecasts:
        r = json.loads(f.result_json)
        responses.append(ForecastResponse(
            id=f.id,
            dates=r.get("dates", []),
            values=r.get("values", []),
            lower_bound=r.get("lower_bound"),
            upper_bound=r.get("upper_bound"),
            detailed_records=r.get("records"),
            created_at=f.created_at,
        ))
    return responses
