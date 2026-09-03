import json
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db
from app.models.user import User
from app.models.schedule import ScheduleConfig
from app.schemas.schedule import ScheduleConfigCreate, ScheduleConfigUpdate, ScheduleConfigResponse
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedules", tags=["schedules"])


def compute_next_run(schedule: ScheduleConfig) -> datetime:
    now = datetime.utcnow()
    base = now.replace(hour=schedule.hour, minute=schedule.minute, second=0, microsecond=0)
    if base <= now:
        base += timedelta(days=1)
    if schedule.schedule_type == "daily":
        return base
    elif schedule.schedule_type == "weekly":
        days_ahead = (schedule.day_of_week - base.weekday()) % 7
        return base + timedelta(days=days_ahead)
    elif schedule.schedule_type == "monthly":
        if base.day > schedule.day_of_month:
            if base.month == 12:
                base = base.replace(year=base.year + 1, month=1, day=schedule.day_of_month)
            else:
                base = base.replace(month=base.month + 1, day=schedule.day_of_month)
        else:
            base = base.replace(day=schedule.day_of_month)
        return base
    return base


@router.get("/", response_model=list[ScheduleConfigResponse])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ScheduleConfig)
        .where(ScheduleConfig.user_id == current_user.id)
        .order_by(ScheduleConfig.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ScheduleConfigResponse)
async def create_schedule(
    payload: ScheduleConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = ScheduleConfig(
        user_id=current_user.id,
        name=payload.name,
        dataset_id=payload.dataset_id,
        dataset_name=payload.dataset_name,
        models_json=json.dumps(payload.models),
        hyper_params_json=json.dumps(payload.hyper_params),
        seasonality_period=payload.seasonality_period,
        date_format=payload.date_format,
        schedule_type=payload.schedule_type,
        day_of_week=payload.day_of_week,
        day_of_month=payload.day_of_month,
        hour=payload.hour,
        minute=payload.minute,
        is_active=True,
    )
    record.next_run_at = compute_next_run(record)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.patch("/{schedule_id}", response_model=ScheduleConfigResponse)
async def update_schedule(
    schedule_id: str,
    payload: ScheduleConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ScheduleConfig).where(
            ScheduleConfig.id == schedule_id,
            ScheduleConfig.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "models" in update_data:
        record.models_json = json.dumps(update_data.pop("models"))
    if "hyper_params" in update_data:
        record.hyper_params_json = json.dumps(update_data.pop("hyper_params"))
    for key, val in update_data.items():
        setattr(record, key, val)
    if "schedule_type" in update_data or "hour" in update_data or "minute" in update_data or "day_of_week" in update_data or "day_of_month" in update_data:
        record.next_run_at = compute_next_run(record)

    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ScheduleConfig).where(
            ScheduleConfig.id == schedule_id,
            ScheduleConfig.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(record)
    await db.commit()
    return {"detail": "Schedule deleted"}
