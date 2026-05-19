import time
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# In-process TTL cache — lives as long as the MCP server process.
# Historical F1 data never changes, so this is safe.
_store: dict[str, tuple[Any, float]] = {}

HISTORICAL_TTL = 60 * 60 * 24 * 365  # 1 year for past seasons
CURRENT_TTL = 60 * 60              # 1 hour for current season data
DEFAULT_TTL = 60 * 60 * 24         # 24 hours default


def _current_season() -> int:
    return time.localtime().tm_year


def ttl_for_year(year: int) -> int:
    return HISTORICAL_TTL if year < _current_season() else CURRENT_TTL


def get(key: str) -> Optional[Any]:
    entry = _store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _store[key]
        return None
    return value


def set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    _store[key] = (value, time.time() + ttl)


def make_key(*parts) -> str:
    return ":".join(str(p) for p in parts)
