# app/services/graph_rag_service.py
from __future__ import annotations

from typing import Dict, List, Any, Optional

from app.services.graph_rerank_service import rerank_foreign_pool_with_graph


def _dedupe_foreign_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[tuple, Dict[str, Any]] = {}

    for item in items or []:
        meta = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
        key = (
            meta.get("country"),
            meta.get("display_path"),
            meta.get("article_number") or (meta.get("structure", {}) or {}).get("article_number"),
        )
        prev = best.get(key)
        if prev is None or float(item.get("final_score", item.get("score", 0.0))) > float(prev.get("final_score", prev.get("score", 0.0))):
            best[key] = item

    return list(best.values())


def match_foreign_to_korean_with_graph(
    *,
    query: str,
    korean_chunks: List[Dict[str, Any]],
    foreign_pool: List[Dict[str, Any]],
    top_k_per_korean: int = 50,
    target_country: Optional[str] = None,
    candidate_limit: int = 80,
    rerank_weight: float = 0.75,
    graph_weight: float = 0.25,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    한국 anchor별 graph-aware foreign matching.
    반환 형태:
    {
        "kr_chunk_id_1": [foreign_cand1, foreign_cand2, ...],
        ...
    }
    """
    out: Dict[str, List[Dict[str, Any]]] = {}

    if not korean_chunks or not foreign_pool:
        return out

    for kr in korean_chunks:
        kr_id = kr.get("chunk_id") or "unknown_kr"
        reranked = rerank_foreign_pool_with_graph(
            query=query,
            korean_chunk=kr,
            foreign_pool=foreign_pool,
            target_country=target_country,
            top_k=top_k_per_korean,
            candidate_limit=candidate_limit,
            rerank_weight=rerank_weight,
            graph_weight=graph_weight,
        )
        reranked = _dedupe_foreign_candidates(reranked)
        reranked.sort(key=lambda x: x.get("final_score", x.get("score", 0.0)), reverse=True)
        out[str(kr_id)] = reranked[:max(1, top_k_per_korean)]

    return out