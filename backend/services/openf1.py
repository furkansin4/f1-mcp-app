import httpx
import logging

OPENF1_BASE = "https://api.openf1.org/v1"

logger = logging.getLogger(__name__)


def get(endpoint: str, params: dict) -> list:
    """Synchronous OpenF1 API request."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{OPENF1_BASE}/{endpoint}", params={k: v for k, v in params.items() if v is not None})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenF1 HTTP error {e.response.status_code} for {endpoint}: {e}")
        return []
    except Exception as e:
        logger.error(f"OpenF1 request failed for {endpoint}: {e}")
        return []


