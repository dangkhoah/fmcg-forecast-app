import httpx
from app.config import settings


async def call_forecast_model(data: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.FORECAST_API_URL,
            json=data,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()
