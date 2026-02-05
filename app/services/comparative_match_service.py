# app/services/comparative_match_service.py

from typing import List, Dict
from app.services.comparative_cache import get_search_cache
from app.services.hybrid_search_service import clamp01


def match_foreign_by_korean(
    search_id: str,
    korean_text: str,
    target_country: str,
    top_k: int = 5,
) -> List[Dict]:

    from app.services.reranker_service import rerank

    foreign_pool = get_search_cache(search_id)
    if not foreign_pool:
        raise ValueError("검색 캐시가 만료되었거나 존재하지 않습니다.")

    # 1. 선택된 국가만 필터링
    candidates = [
        r for r in foreign_pool
        if r.get("metadata", {}).get("country") == target_country
    ]

    if not candidates:
        return []

    # 2. reranker만 사용
    reranked = rerank(
        query=korean_text,
        cands=candidates,
        top_k=top_k,
    )

    # 3. display_score 정규화
    for r in reranked:
        base = r.get("re_score", r.get("fusion_score", 0.0))
        r["display_score"] = clamp01(base)

    return reranked
