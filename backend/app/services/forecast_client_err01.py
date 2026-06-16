# app/services/forecast_client.py (ASSUMED CONTENT)
import httpx
import json
import logging
from app.config import settings
from app.services.model_cache import forecast_model_cache
from typing import Dict, Any, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def _get_model_service_base_url() -> str:
    """
    Derives the base URL from configuration, ensuring no trailing paths 
    like '/predict' or trailing slashes interfere with endpoint construction.
    """
    parsed = urlparse(settings.MODEL_SERVICE_URL)
    return f"{parsed.scheme}://{parsed.netloc}"

async def verify_model_service_connectivity() -> bool:
    """
    Checks if the model service is reachable and responding correctly.
    This should be called during the backend's startup sequence.
    """
    logger.info(f"Final loaded configuration for MODEL_SERVICE_URL: {settings.MODEL_SERVICE_URL}")
    base_url = _get_model_service_base_url()
    url = f"{base_url}/health"
    try:
        async with httpx.AsyncClient() as client:
            logger.debug(f"Verifying model service connectivity at: {url}")
            # Use a conservative timeout for startup validation
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            health_data = response.json()
            logger.info(f"Model service connection verified at {url}: {health_data}")
            return True
    except Exception as e:
        logger.error(f"Startup validation failed: Model service at {url} is unreachable. Error: {e}")
        return False

async def call_forecast_model(
    dataset_id: str, # Added dataset_id for caching
    model_input: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calls the external forecast model service, with caching logic.
    """
    force_retrain = model_input.pop("force_retrain", False)

    # Create a cache key from relevant parameters
    # file_path is derived from dataset_id, so dataset_id is sufficient.
    # additional_params is guaranteed to be a dict (possibly empty) due to payload spreading.
    cache_key_params = {k: v for k, v in model_input.items() if k != "file_path"}
    
    # Ensure additional_params is hashable if present
    if "additional_params" in cache_key_params:
        cache_key_params["additional_params"] = frozenset(cache_key_params["additional_params"].items())
    else:
        # If not present, ensure it's consistently represented for caching
        cache_key_params["additional_params"] = frozenset()

    # Sort items to ensure consistent key generation regardless of dict insertion order
    cache_key = (dataset_id, ) + tuple(sorted(cache_key_params.items()))

    if not force_retrain:
        cached_result = forecast_model_cache.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached forecast result for dataset_id={dataset_id}")
            cached_result["cached"] = True # Indicate that this result came from cache
            return cached_result

    logger.info(f"Calling external model service for dataset_id={dataset_id}, force_retrain={force_retrain}")
    logger.info(f"Final model_input sent to model service: {model_input}")
    base_url = _get_model_service_base_url()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/predict",
            json=model_input,
            timeout=settings.MODEL_SERVICE_TIMEOUT
        )
        response.raise_for_status()
        model_result = response.json()
        forecast_model_cache.put(cache_key, model_result)
        return model_result
