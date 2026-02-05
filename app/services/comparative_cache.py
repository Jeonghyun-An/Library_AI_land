# app/services/comparative_cache.py
"""
비교 검색 캐시 서비스
- 검색 결과를 메모리에 캐싱 (재매칭 시 재사용)
- TTL: 30분
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import threading

# 캐시 저장소
_cache: Dict[str, Dict] = {}
_cache_lock = threading.Lock()

# 캐시 TTL (초)
CACHE_TTL_SECONDS = 1800  # 30분


def set_search_cache(search_id: str, results: List[Dict]) -> None:
    """
    검색 결과 캐싱
    
    Args:
        search_id: 검색 ID
        results: 검색 결과 리스트
    """
    with _cache_lock:
        _cache[search_id] = {
            "results": results,
            "timestamp": datetime.now()
        }
    
    # 캐시 정리 (백그라운드)
    _cleanup_old_cache()


def get_search_cache(search_id: str) -> Optional[List[Dict]]:
    """
    캐시된 검색 결과 가져오기
    
    Args:
        search_id: 검색 ID
    
    Returns:
        검색 결과 리스트 (만료 시 None)
    """
    with _cache_lock:
        if search_id not in _cache:
            return None
        
        cached = _cache[search_id]
        timestamp = cached["timestamp"]
        
        # TTL 체크
        if datetime.now() - timestamp > timedelta(seconds=CACHE_TTL_SECONDS):
            del _cache[search_id]
            return None
        
        return cached["results"]


def _cleanup_old_cache() -> None:
    """오래된 캐시 정리"""
    with _cache_lock:
        now = datetime.now()
        expired_keys = [
            key for key, value in _cache.items()
            if now - value["timestamp"] > timedelta(seconds=CACHE_TTL_SECONDS)
        ]
        
        for key in expired_keys:
            del _cache[key]