import os
import json
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.services.forecast_client import get_client
from app.config import settings
from app.models.user import User
from app.models.dataset import Dataset
from app.services.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["train"])

MODEL_SERVICE_BASE = str(settings.MODEL_SERVICE_URL).rstrip("/")


@router.get("/available-models")
async def get_available_models(current_user: User = Depends(get_current_user)):
    client = get_client()
    try:
        resp = await client.get(f"{MODEL_SERVICE_BASE}/available-models", timeout=45.0) # Increased backend HTTP timeout from 10s to 45s so cold-starting Model Services on Render have ample time to respond.
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch available models: {e}")
        raise HTTPException(status_code=502, detail=f"Model service error: {str(e)}")


@router.post("/train")
async def start_training(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    body = await request.json()

    dataset_id = body.get("dataset_id")
    if dataset_id:
        result = await db.execute(
            select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == current_user.id)
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        resolved_path = os.path.join(settings.UPLOAD_DIR, os.path.basename(dataset.file_path))
        body["file_path"] = resolved_path
        body["dataset_name"] = dataset.filename
        body["dataset_row_count"] = dataset.row_count
        if os.path.exists(resolved_path):
            try:
                with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                    body["file_content"] = f.read()
            except Exception as e:
                logger.warning(f"Could not read dataset file content: {e}")

    async def stream_events():
        async with httpx.AsyncClient(timeout=None) as c:
            resp = None
            try:
                resp = await c.send(
                    c.build_request(
                        "POST",
                        f"{MODEL_SERVICE_BASE}/train",
                        json=body,
                        headers={"Accept": "text/event-stream"},
                    ),
                    stream=True,
                )
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes():
                    yield chunk
            except Exception as e:
                logger.error(f"Training stream failed: {e}")
                yield f"data: {json.dumps({'error': True, 'message': str(e)})}\n\n".encode()
            finally:
                if resp is not None:
                    await resp.aclose()

    return StreamingResponse(stream_events(), media_type="text/event-stream")
