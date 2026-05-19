import httpx
import logging
from typing import Optional

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


def get_session_key(year: int, event_name: str, session_name: str) -> Optional[int]:
    """Find the OpenF1 session_key for a given race and session type."""
    sessions = get("sessions", {"year": year, "session_name": session_name})
    event_lower = event_name.lower()
    for s in sessions:
        location = s.get("location", "").lower()
        country = s.get("country_name", "").lower()
        circuit = s.get("circuit_short_name", "").lower()
        if event_lower in location or event_lower in country or event_lower in circuit:
            return s.get("session_key")
    return None
