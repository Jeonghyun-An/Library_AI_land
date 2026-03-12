# app/services/graph_rerank_service.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from app.services.graph_service import is_graph_enabled, run_read
from app.services.hybrid_search_service import normalize_scores_minmax
from app.services.reranker_service import rerank


_GRAPH_EVIDENCE_CACHE: Dict[str, Dict[str, Any]] = {}


def _ensure_meta_dict(meta: Any) -> Dict[str, Any]:
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str):
        try:
            import json
            v = json.loads(meta)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    try:
        return dict(meta)
    except Exception:
        return {}


def _safe_text(cand: Dict[str, Any]) -> str:
    return (
        cand.get("chunk")
        or _ensure_meta_dict(cand.get("metadata")).get("korean_text")
        or _ensure_meta_dict(cand.get("metadata")).get("english_text")
        or ""
    )


def _pick(meta: Dict[str, Any], key: str, default=None):
    if key in meta:
        return meta.get(key, default)
    structure = meta.get("structure", {})
    if isinstance(structure, dict) and key in structure:
        return structure.get(key, default)
    return default


def _normalize_article_number(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _normalize_paragraph(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _resolve_article_ids_from_meta(meta: Dict[str, Any]) -> List[str]:
    """
    metadata 기반으로 Neo4j Article.article_id 후보를 조회.
    article_id가 metadata에 이미 있으면 우선 사용.
    """
    meta = _ensure_meta_dict(meta)

    # 1) 이미 article_id가 있으면 최우선
    for key in ("article_id",):
        if meta.get(key):
            return [str(meta[key])]

    country = meta.get("country") or meta.get("country_code")
    article_number = _normalize_article_number(
        meta.get("article_number") or _pick(meta, "article_number")
    )
    paragraph = _normalize_paragraph(
        meta.get("paragraph") or _pick(meta, "paragraph")
    )
    version = (
        meta.get("constitution_version")
        or meta.get("doc_version")
        or _pick(meta, "constitution_version")
        or _pick(meta, "doc_version")
    )

    if not country or not article_number:
        return []

    # paragraph / version이 있으면 더 정확히
    where_parts = ["a.country_code = $country", "a.article_number = $article_number"]
    params: Dict[str, Any] = {
        "country": str(country),
        "article_number": str(article_number),
        "limit": 5,
    }

    if paragraph:
        where_parts.append("coalesce(a.paragraph, '') = $paragraph")
        params["paragraph"] = str(paragraph)

    order_by = """
    ORDER BY
      CASE WHEN $version IS NOT NULL AND a.doc_version = $version THEN 0 ELSE 1 END,
      CASE WHEN a.paragraph IS NULL OR a.paragraph = '' THEN 0 ELSE 1 END,
      a.seq ASC
    """
    params["version"] = str(version) if version else None

    query = f"""
    MATCH (a:Article)
    WHERE {' AND '.join(where_parts)}
    RETURN a.article_id AS article_id
    {order_by}
    LIMIT $limit
    """
    rows = run_read(query, params)
    return [str(r["article_id"]) for r in rows if r.get("article_id")]


def _load_article_evidence(article_ids: List[str]) -> Dict[str, Any]:
    """
    Neo4j에서 조항의 concept / compare target / neighbor 정보를 읽어온다.
    """
    if not article_ids or not is_graph_enabled():
        return {
            "article_ids": [],
            "concept_keys": set(),
            "concept_names": set(),
            "compare_targets": set(),
            "neighbor_articles": set(),
        }

    cache_key = "|".join(sorted(article_ids))
    cached = _GRAPH_EVIDENCE_CACHE.get(cache_key)
    if cached:
        return cached

    query = """
    MATCH (a:Article)
    WHERE a.article_id IN $article_ids
    OPTIONAL MATCH (a)-[:RELATES_TO_CONCEPT]->(c:Concept)
    OPTIONAL MATCH (a)-[:COMPARES_TO]->(fx:Article)
    OPTIONAL MATCH (a)-[:NEXT_ARTICLE|PREV_ARTICLE]->(n:Article)
    RETURN
      collect(DISTINCT a.article_id) AS article_ids,
      collect(DISTINCT c.key) AS concept_keys,
      collect(DISTINCT c.name) AS concept_names,
      collect(DISTINCT fx.article_id) AS compare_targets,
      collect(DISTINCT n.article_id) AS neighbor_articles
    """
    rows = run_read(query, {"article_ids": article_ids})
    if not rows:
        result = {
            "article_ids": article_ids,
            "concept_keys": set(),
            "concept_names": set(),
            "compare_targets": set(),
            "neighbor_articles": set(),
        }
        _GRAPH_EVIDENCE_CACHE[cache_key] = result
        return result

    row = rows[0]
    result = {
        "article_ids": [x for x in (row.get("article_ids") or []) if x],
        "concept_keys": set(x for x in (row.get("concept_keys") or []) if x),
        "concept_names": set(x for x in (row.get("concept_names") or []) if x),
        "compare_targets": set(x for x in (row.get("compare_targets") or []) if x),
        "neighbor_articles": set(x for x in (row.get("neighbor_articles") or []) if x),
    }
    _GRAPH_EVIDENCE_CACHE[cache_key] = result
    return result


def _compute_graph_score(
    *,
    korean_evidence: Dict[str, Any],
    foreign_evidence: Dict[str, Any],
    foreign_meta: Dict[str, Any],
    target_country: Optional[str] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    graph score를 0~1에 가깝게 계산.
    """
    concept_overlap = korean_evidence["concept_keys"] & foreign_evidence["concept_keys"]
    concept_name_overlap = korean_evidence["concept_names"] & foreign_evidence["concept_names"]
    direct_compare = bool(
        foreign_evidence["article_ids"] and
        any(aid in korean_evidence["compare_targets"] for aid in foreign_evidence["article_ids"])
    )
    neighbor_hit = bool(
        foreign_evidence["article_ids"] and
        any(aid in korean_evidence["neighbor_articles"] for aid in foreign_evidence["article_ids"])
    )

    country_match = False
    if target_country:
        country_match = (foreign_meta.get("country") == target_country)

    article_number_bonus = 0.0
    kr_article_nums = set()
    for aid in korean_evidence["article_ids"]:
        # KR:1987:10 또는 KR:1987:10:1
        parts = str(aid).split(":")
        if len(parts) >= 3:
            kr_article_nums.add(parts[2])

    fx_article_number = _normalize_article_number(
        foreign_meta.get("article_number") or _pick(foreign_meta, "article_number")
    )
    if fx_article_number and fx_article_number in kr_article_nums:
        article_number_bonus = 0.06

    score = 0.0
    score += min(len(concept_overlap) * 0.12, 0.36)
    score += min(len(concept_name_overlap) * 0.08, 0.24)
    if direct_compare:
        score += 0.28
    if neighbor_hit:
        score += 0.06
    if country_match:
        score += 0.08
    score += article_number_bonus

    score = max(0.0, min(1.0, score))

    evidence = {
        "concept_overlap_keys": sorted(list(concept_overlap))[:10],
        "concept_overlap_names": sorted(list(concept_name_overlap))[:10],
        "direct_compare_hit": direct_compare,
        "neighbor_hit": neighbor_hit,
        "target_country_match": country_match,
        "matched_article_ids": foreign_evidence["article_ids"][:5],
    }
    return score, evidence


def rerank_foreign_pool_with_graph(
    *,
    query: str,
    korean_chunk: Dict[str, Any],
    foreign_pool: List[Dict[str, Any]],
    target_country: Optional[str] = None,
    top_k: int = 50,
    candidate_limit: int = 80,
    rerank_weight: float = 0.75,
    graph_weight: float = 0.25,
) -> List[Dict[str, Any]]:
    """
    단일 한국 조항(anchor)에 대해 foreign pool을 graph-aware rerank.
    반환 형식은 기존 foreign match 결과와 최대한 호환되게 유지.
    """
    if not foreign_pool:
        return []

    rerank_weight = max(0.0, min(1.0, float(rerank_weight)))
    graph_weight = max(0.0, min(1.0, float(graph_weight)))
    total = rerank_weight + graph_weight
    if total <= 0:
        rerank_weight, graph_weight = 0.8, 0.2
        total = 1.0
    rerank_weight /= total
    graph_weight /= total

    korean_meta = _ensure_meta_dict(korean_chunk.get("metadata"))
    korean_text = korean_chunk.get("chunk") or ""

    candidates = []
    for cand in foreign_pool:
        meta = _ensure_meta_dict(cand.get("metadata"))
        if meta.get("country") == "KR":
            continue
        if target_country and meta.get("country") != target_country:
            continue
        c = dict(cand)
        c["metadata"] = meta
        c["chunk"] = _safe_text(c)
        candidates.append(c)

    if not candidates:
        return []

    candidates = candidates[:max(1, candidate_limit)]

    # 1) 텍스트 rerank
    try:
        reranked = rerank(
            query=korean_text or query,
            cands=candidates,
            top_k=len(candidates),
        )
    except Exception:
        reranked = candidates

    # 2) 한국 anchor graph evidence
    korean_article_ids = _resolve_article_ids_from_meta(korean_meta)
    korean_evidence = _load_article_evidence(korean_article_ids)

    # 3) foreign candidate별 graph score 계산
    rerank_scores_raw: List[float] = []
    graph_scores_raw: List[float] = []

    for cand in reranked:
        meta = _ensure_meta_dict(cand.get("metadata"))
        article_ids = _resolve_article_ids_from_meta(meta)
        foreign_evidence = _load_article_evidence(article_ids)

        graph_score, graph_evidence = _compute_graph_score(
            korean_evidence=korean_evidence,
            foreign_evidence=foreign_evidence,
            foreign_meta=meta,
            target_country=target_country,
        )

        cand["graph_score"] = float(graph_score)
        cand["graph_evidence"] = graph_evidence
        cand["article_ids"] = article_ids

        rerank_scores_raw.append(float(cand.get("re_score", cand.get("score", 0.0))))
        graph_scores_raw.append(float(graph_score))

    rerank_scores_norm = normalize_scores_minmax(rerank_scores_raw)
    graph_scores_norm = normalize_scores_minmax(graph_scores_raw)

    final_scores_raw: List[float] = []
    for idx, cand in enumerate(reranked):
        rr = float(rerank_scores_norm[idx])
        gg = float(graph_scores_norm[idx])
        final_score = (rr * rerank_weight) + (gg * graph_weight)

        cand["rerank_score_norm"] = rr
        cand["graph_score_norm"] = gg
        cand["final_score"] = final_score
        final_scores_raw.append(final_score)

    final_scores_norm = normalize_scores_minmax(final_scores_raw)
    for idx, cand in enumerate(reranked):
        # 기존 comparative router가 기대하는 필드 유지
        cand["raw_score"] = float(cand.get("final_score", 0.0))
        cand["display_score"] = float(final_scores_norm[idx])
        cand["score"] = float(final_scores_norm[idx])

    reranked.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
    return reranked[:max(1, top_k)]