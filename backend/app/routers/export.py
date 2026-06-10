import json
import sys
import os
import traceback
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.forecast import ForecastResult
from app.services.auth import get_current_user
from app.services.export import export_csv, export_excel

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/{forecast_id}")
async def export_forecast(
    forecast_id: str,
    format: str = Query("csv", regex="^(csv|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ForecastResult).where(
            ForecastResult.id == forecast_id,
            ForecastResult.user_id == current_user.id,
        )
    )
    forecast = result.scalar_one_or_none()
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast result not found.")

    try:
        data = json.loads(forecast.result_json)
        dates = data.get("dates", [])
        values = data.get("values", [])
        lower = data.get("lower_bound")
        upper = data.get("upper_bound")
        records = data.get("records")

        if format == "csv":
            return export_csv(dates, values, lower, upper, records)
        return export_excel(dates, values, lower, upper, records)
    except Exception as e:
        # Extract detailed traceback information
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb = traceback.extract_tb(exc_traceback)[-1]  # Get the last frame
        file_name = os.path.basename(tb.filename)
        line_number = tb.lineno
        
        error_detail = f"Export error: {str(e)} (File: {file_name}, Line: {line_number})"
        print(traceback.format_exc())  # Print full trace to server logs
        raise HTTPException(status_code=500, detail=error_detail)
