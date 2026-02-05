# app/services/comparative_cache.py

from typing import Dict, List, Any
import time

_COMPARATIVE_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 60 * 10  # 10분


def set_search_cache(search_id: str, foreign_pool: List[Dict]):
    _COMPARATIVE_CACHE[search_id] = {
        "ts": time.time(),
        "foreign_pool": foreign_pool,
    }


def get_search_cache(search_id: str) -> List[Dict] | None:
    item = _COMPARATIVE_CACHE.get(search_id)
    if not item:
        return None

    if time.time() - item["ts"] > _CACHE_TTL:
        _COMPARATIVE_CACHE.pop(search_id, None)
        return None

    return item["foreign_pool"]
