import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.user import User
from app.models.training import TrainingHistory
from app.schemas.training import TrainingHistoryResponse, TrainingSaveRequest
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])


@router.post("/save", response_model=TrainingHistoryResponse)
async def save_training_result(
    payload: TrainingSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = TrainingHistory(
        user_id=current_user.id,
        dataset_id=payload.dataset_id,
        dataset_name=payload.dataset_name,
        # model_key=payload.model_key,
        dataset_row_count=payload.dataset_row_count,
        model_name=payload.model_name,
        hyper_params_json=json.dumps(payload.hyper_params),
        mape=payload.mape,
        training_time=payload.training_time,
        status=payload.status,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/history", response_model=list[TrainingHistoryResponse])
async def training_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TrainingHistory)
        .where(TrainingHistory.user_id == current_user.id)
        .order_by(TrainingHistory.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{record_id}")
async def delete_training_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TrainingHistory).where(
            TrainingHistory.id == record_id,
            TrainingHistory.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Training record not found")
    await db.delete(record)
    await db.commit()
    return {"detail": "Training record deleted"}
