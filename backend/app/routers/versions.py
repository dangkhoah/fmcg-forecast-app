import json
import logging
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.version import PredictionVersion
from app.schemas.version import VersionSaveRequest, VersionResponse, ComparisonResponse, ComparisonPoint
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecast/versions", tags=["versions"])


@router.post("/save", response_model=VersionResponse)
async def save_version(
    payload: VersionSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = PredictionVersion(
        user_id=current_user.id,
        forecast_id=payload.forecast_id,
        dataset_id=payload.dataset_id,
        dataset_name=payload.dataset_name,
        version_label=payload.version_label,
        notes=payload.notes,
        parameters_json=json.dumps(payload.parameters),
        result_json=json.dumps(payload.result),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/", response_model=list[VersionResponse])
async def list_versions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PredictionVersion)
        .where(PredictionVersion.user_id == current_user.id)
        .order_by(PredictionVersion.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{version_id}")
async def delete_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PredictionVersion).where(
            PredictionVersion.id == version_id,
            PredictionVersion.user_id == current_user.id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Version not found")
    await db.delete(record)
    await db.commit()
    return {"detail": "Version deleted"}


@router.get("/compare", response_model=ComparisonResponse)
async def compare_versions(
    ids: str = Query(..., description="Comma-separated version IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    version_ids = [v.strip() for v in ids.split(",") if v.strip()]
    if len(version_ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 version IDs to compare")

    result = await db.execute(
        select(PredictionVersion).where(
            PredictionVersion.id.in_(version_ids),
            PredictionVersion.user_id == current_user.id,
        )
    )
    versions = result.scalars().all()
    if len(versions) != len(version_ids):
        raise HTTPException(status_code=404, detail="One or more versions not found")

    dates_map = defaultdict(dict)
    for v in versions:
        try:
            data = json.loads(v.result_json)
            dates = data.get("dates", [])
            values = data.get("values", [])
            for d, val in zip(dates, values):
                dates_map[d][v.version_label] = val
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    comparison_data = [
        ComparisonPoint(date=date, values=vals)
        for date, vals in sorted(dates_map.items())
    ]

    return ComparisonResponse(
        versions=[VersionResponse.model_validate(v) for v in versions],
        comparison_data=comparison_data,
    )
