# app/services/comparative_match_service.py
"""
비교 매칭 서비스
- 한국 조항 클릭 시 특정 국가 헌법 재매칭
- 캐시된 검색 결과 활용
"""

from typing import List, Dict
from app.services.comparative_cache import get_search_cache
from app.services.hybrid_search_service import normalize_scores_minmax


def match_foreign_by_korean(
    search_id: str,
    korean_text: str,
    target_country: str,
    top_k: int = 5,
) -> List[Dict]:
    """
    한국 조항 텍스트로 특정 국가 헌법 재매칭
    
    Args:
        search_id: 검색 캐시 ID
        korean_text: 한국 조항 텍스트
        target_country: 타겟 국가 코드
        top_k: 반환할 결과 수
    
    Returns:
        매칭된 외국 조항 리스트 (raw_score, score, display_score 포함)
    """
    from app.services.reranker_service import rerank

    # 캐시에서 외국 조항 풀 가져오기
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

    # 2. reranker로 재매칭
    reranked = rerank(
        query=korean_text,
        cands=candidates,
        top_k=top_k,
    )

    # 3. 점수 정규화
    raw_scores = [r.get("re_score", r.get("fusion_score", 0.0)) for r in reranked]
    normalized = normalize_scores_minmax(raw_scores)
    
    for i, r in enumerate(reranked):
        r["raw_score"] = raw_scores[i]
        r["score"] = raw_scores[i]
        r["display_score"] = normalized[i]

    return reranked