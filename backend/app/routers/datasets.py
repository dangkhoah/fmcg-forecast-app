import json
import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.schemas.dataset import DatasetResponse, DatasetPreview
from app.services.auth import get_current_user
from app.utils.csv_parser import parse_file

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetResponse, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.endswith((".csv", ".xls", ".xlsx")):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")

    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    saved_name = f"{file_id}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, saved_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    df = parse_file(file.filename, content)

    dataset = Dataset(
        id=file_id,
        user_id=current_user.id,
        filename=file.filename,
        file_path=file_path,
        row_count=len(df),
        columns_json=json.dumps(list(df.columns)),
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/", response_model=list[DatasetResponse])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.user_id == current_user.id).order_by(Dataset.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{dataset_id}/preview", response_model=DatasetPreview)
async def preview_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404)

    import pandas as pd
    df = pd.read_csv(dataset.file_path) if dataset.file_path.endswith(".csv") else pd.read_excel(dataset.file_path)
    preview = df.head(50)

    return DatasetPreview(
        columns=list(df.columns),
        rows=preview.values.tolist(),
        total_rows=len(df),
    )


@router.delete("/{dataset_id}", status_code=204)
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404)

    if os.path.exists(dataset.file_path):
        os.remove(dataset.file_path)

    await db.delete(dataset)
    await db.commit()
