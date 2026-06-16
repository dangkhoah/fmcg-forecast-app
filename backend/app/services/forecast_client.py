import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Global client singleton
_client: httpx.AsyncClient | None = None

def get_client() -> httpx.AsyncClient:
    """Provides access to the shared client instance."""
    global _client
    if _client is None:
        # We initialize with a long timeout suitable for ML tasks
        _client = httpx.AsyncClient(timeout=120.0)
    return _client

async def close_client():
    """Closes the shared client during application shutdown."""
    global _client
    if _client:
        await _client.aclose()
        _client = None

async def call_forecast_model(data: dict) -> dict:
    client = get_client()
    try:
        resp = await client.post(
            settings.FORECAST_API_URL,
            json=data
        )
        
        # If the model service returned a 4xx or 5xx status code
        if resp.is_error:
            try:
                # Attempt to extract the "detail" message sent by the model service
                error_data = resp.json()
                error_msg = error_data.get("detail", resp.text)
            except Exception:
                error_msg = resp.text
            
            logger.error(f"Model Service Error (Status {resp.status_code}): {error_msg}")
            raise Exception(error_msg)

        return resp.json()

    except httpx.TimeoutException:
        logger.error("Forecast model request timed out")
        raise Exception("The forecast engine took too long to respond. The dataset might be too large.")
    except httpx.RequestError as exc:
        logger.error(f"Network error connecting to model service: {exc}")
        raise Exception("Could not connect to the forecast engine. Please ensure the model service is running.")
