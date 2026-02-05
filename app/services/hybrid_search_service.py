# app/services/hybrid_search_service.py
"""
하이브리드 검색 서비스 (FULL PATCH)
- Dense(벡터) + Sparse(BM25-like rank) + Keyword(조항번호) → RRF Fusion
- BM25 raw score 제거 → rank-only signal (Sparse 영향 과대 방지)
- reranker 이후 score_threshold 적용 (정확한 필터링)
- display_score(0~1) 분리 (프론트 % 폭주 방지)
- Sparse corpus 범위 제한(expr) + doc_type 필터 기본 적용 (노이즈/비용 절감)
- match_foreign_to_korean() 포함 (한국 클릭 → 외국 재매칭에 사용 가능)
"""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional
from collections import defaultdict


# =========================
# Sparse (rank-only)
# =========================
class BM25RankOnly:
    """
    '진짜 BM25' 대신:
    - 구현/비용 단순화
    - raw score 폭주 제거
    - rank-only signal로 RRF에 안정적으로 반영

    현재는 "쿼리 토큰과 문서 토큰의 overlap" 기반으로 순위만 만들고,
    점수는 순위 기반(1/(rank+1))으로만 부여한다.
    """

    def fit(self, corpus: List[str]):
        # fit 유지(확장 여지), 현재는 필요 없음
        return

    def rank(self, query: str, corpus: List[str]) -> List[int]:
        q_terms = set(query.lower().split())
        scored = []
        for idx, text in enumerate(corpus):
            terms = set((text or "").lower().split())
            overlap = len(q_terms & terms)
            scored.append((idx, overlap))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [idx for idx, _ in scored]


# =========================
# Utils
# =========================
def extract_article_numbers(query: str) -> List[str]:
    nums: List[str] = []
    nums += re.findall(r"제\s*(\d+)\s*조", query)
    nums += re.findall(r"Article\s*\(?\s*(\d+)\s*\)?", query, re.IGNORECASE)
    # unique
    return list(set(nums))


def clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, x))


def _ensure_meta_dict(meta: Any) -> Dict[str, Any]:
    # router 쪽에도 비슷한 함수가 있지만, 서비스 단에서 안전장치
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    # 문자열 JSON이면 라우터에서 풀어주기도 하지만 여기서도 시도해둠
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


def _hit_field(hit: Any, field: str, default=None):
    """
    PyMilvus hit/entity 접근 호환:
    - hit.entity 가 dict 인 경우
    - hit.entity 가 Entity 객체인 경우
    - hit 자체가 dict-like 인 경우
    """
    ent = getattr(hit, "entity", None)
    if ent is not None:
        if isinstance(ent, dict):
            return ent.get(field, default)
        if hasattr(ent, field):
            try:
                return getattr(ent, field)
            except Exception:
                pass
        try:
            return ent[field]
        except Exception:
            pass

    if isinstance(hit, dict):
        return hit.get(field, default)

    try:
        return hit.get(field)
    except Exception:
        return default


# =========================
# RRF Fusion
# =========================
def rrf_fusion(
    dense_results: List[Dict[str, Any]],
    sparse_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    dense_weight: float = 0.5,
    sparse_weight: float = 0.3,
    keyword_weight: float = 0.2,
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    RRF(Reciprocal Rank Fusion):
    score = Σ weight * 1/(k + rank)

    - raw score를 섞지 않아서 점수 폭주/스케일 문제 없음
    """
    total = dense_weight + sparse_weight + keyword_weight
    if total <= 0:
        dense_weight, sparse_weight, keyword_weight = 1.0, 0.0, 0.0
        total = 1.0

    dense_weight /= total
    sparse_weight /= total
    keyword_weight /= total

    fused: Dict[str, Dict[str, Any]] = {}

    def _add(rank: int, result: Dict[str, Any], weight: float, rank_key: str):
        cid = result.get("chunk_id") or result.get("doc_id")
        if not cid:
            return
        rrf_score = weight * (1.0 / (k + rank + 1))

        if cid not in fused:
            fused[cid] = {
                **result,
                "fusion_score": 0.0,
                "dense_rank": None,
                "sparse_rank": None,
                "keyword_rank": None,
            }

        fused[cid]["fusion_score"] += rrf_score
        fused[cid][rank_key] = rank + 1

    for r, res in enumerate(dense_results or []):
        _add(r, res, dense_weight, "dense_rank")

    for r, res in enumerate(sparse_results or []):
        _add(r, res, sparse_weight, "sparse_rank")

    for r, res in enumerate(keyword_results or []):
        _add(r, res, keyword_weight, "keyword_rank")

    return sorted(fused.values(), key=lambda x: x.get("fusion_score", 0.0), reverse=True)


# =========================
# Public APIs
# =========================
def hybrid_search(
    query: str,
    collection,
    embedding_model,
    top_k: int = 10,
    initial_retrieve: int = 100,
    country_filter: Optional[str] = None,
    use_reranker: bool = True,
    score_threshold: Optional[float] = None,
    min_results: int = 1,
    doc_type_filter: str = "constitution",
    sparse_corpus_limit: int = 1000,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.3,
    keyword_weight: float = 0.2,
) -> List[Dict[str, Any]]:
    """
    하이브리드 검색

    핵심 포인트:
    - Sparse는 raw score를 쓰지 않고 rank-only signal로만 반영
    - 최종 필터(score_threshold)는 reranker 이후 적용
    - 프론트 표기용 display_score(0~1)를 별도로 제공
    """

    # ---------- expr 구성 ----------
    expr_parts: List[str] = []
    if doc_type_filter:
        expr_parts.append(f'metadata["doc_type"] == "{doc_type_filter}"')
    if country_filter:
        expr_parts.append(f'metadata["country"] == "{country_filter}"')

    expr = " && ".join(expr_parts) if expr_parts else None

    # ---------- Dense ----------
    q_emb = embedding_model.encode([query], normalize_embeddings=True)[0]
    dense_hits = collection.search(
        data=[q_emb.tolist()],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"ef": 256}},
        limit=initial_retrieve,
        expr=expr,
        output_fields=["doc_id", "chunk_text", "metadata"],
    )

    dense: List[Dict[str, Any]] = []
    for hits in dense_hits:
        for r, h in enumerate(hits):
            dense.append(
                {
                    "chunk_id": _hit_field(h, "doc_id"),
                    "chunk": _hit_field(h, "chunk_text"),
                    "score": float(getattr(h, "score", 0.0) or 0.0),  # 내부 참고용
                    "metadata": _hit_field(h, "metadata"),
                    "rank": r + 1,
                }
            )

    # ---------- Sparse (rank-only) ----------
    sparse: List[Dict[str, Any]] = []
    try:
        corpus_docs = collection.query(
            expr=expr or "id >= 0",
            output_fields=["doc_id", "chunk_text", "metadata"],
            limit=min(sparse_corpus_limit, max(initial_retrieve * 3, 200)),
        )
    except Exception:
        corpus_docs = []

    if corpus_docs:
        corpus = [d.get("chunk_text", "") for d in corpus_docs]
        bm25 = BM25RankOnly()
        bm25.fit(corpus)

        ranked_idx = bm25.rank(query, corpus)[:initial_retrieve]
        for r, idx in enumerate(ranked_idx):
            doc = corpus_docs[idx]
            sparse.append(
                {
                    "chunk_id": doc.get("doc_id"),
                    "chunk": doc.get("chunk_text"),
                    "score": 1.0 / (r + 1),  # rank-based (내부 참고용)
                    "metadata": doc.get("metadata"),
                    "rank": r + 1,
                }
            )

    # ---------- Keyword (조항번호) ----------
    keyword: List[Dict[str, Any]] = []
    nums = extract_article_numbers(query)
    if nums:
        for num in nums:
            expr_kw_parts = []
            if doc_type_filter:
                expr_kw_parts.append(f'metadata["doc_type"] == "{doc_type_filter}"')
            expr_kw_parts.append(f'metadata["structure"]["article_number"] == "{num}"')
            if country_filter:
                expr_kw_parts.append(f'metadata["country"] == "{country_filter}"')
            expr_kw = " && ".join(expr_kw_parts)

            try:
                kw_docs = collection.query(
                    expr=expr_kw,
                    output_fields=["doc_id", "chunk_text", "metadata"],
                    limit=10,
                )
            except Exception:
                kw_docs = []

            for r, doc in enumerate(kw_docs):
                keyword.append(
                    {
                        "chunk_id": doc.get("doc_id"),
                        "chunk": doc.get("chunk_text"),
                        "score": 1.0,  # 내부 참고용
                        "metadata": doc.get("metadata"),
                        "rank": r + 1,
                    }
                )

    # ---------- Fusion ----------
    fused = rrf_fusion(
        dense_results=dense,
        sparse_results=sparse,
        keyword_results=keyword,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        keyword_weight=keyword_weight,
        k=60,
    )

    # ---------- Rerank ----------
    reranked = fused
    if use_reranker and fused:
        from app.services.reranker_service import rerank

        # 비용 제어: reranker 후보는 fused 상위만
        cand_size = min(len(fused), max(top_k * 4, 50))
        reranked = rerank(
            query=query,
            cands=fused[:cand_size],
            top_k=cand_size,  # 일단 후보 내에서 전부 점수화
        )

    # ---------- Threshold (AFTER rerank) ----------
    if score_threshold is not None:
        passed = [
            r
            for r in reranked
            if float(r.get("re_score", r.get("fusion_score", 0.0)) or 0.0) >= score_threshold
        ]
        if len(passed) >= min_results:
            reranked = passed
        else:
            reranked = reranked[:min_results]

    # ---------- Display score (0~1) ----------
    for r in reranked:
        base = float(r.get("re_score", r.get("fusion_score", 0.0)) or 0.0)
        r["display_score"] = clamp01(base)

        # metadata가 문자열인 경우에도 프론트/라우터가 다루기 쉽게 정리
        r["metadata"] = _ensure_meta_dict(r.get("metadata"))

    # top_k=0이면 "필터 통과 전부"를 의미하도록 처리
    if top_k and top_k > 0:
        return reranked[:top_k]
    return reranked


def match_foreign_to_korean(
    korean_chunks: List[Dict[str, Any]],
    foreign_pool: List[Dict[str, Any]],
    top_k_per_korean: int = 50,
    use_reranker: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    한국 청크(조항) 각각에 대해 외국 후보 풀에서 유사한 것 매칭
    - router에서 한국 클릭 시 '선택 국가만' 재매칭할 때도 활용 가능

    korean_chunks 예시:
      [{
        "chunk_id": "KR_xxx_12",
        "chunk": "...한국 조항 텍스트...",
        "metadata": {...}
      }]

    foreign_pool 예시:
      hybrid_search()가 반환하는 dict 리스트를 그대로 넣어도 됨
    """
    result: Dict[str, List[Dict[str, Any]]] = {}

    if not korean_chunks:
        return result

    # foreign_pool의 metadata 타입 안전화
    safe_pool = []
    for item in foreign_pool or []:
        item = dict(item)
        item["metadata"] = _ensure_meta_dict(item.get("metadata"))
        safe_pool.append(item)

    if use_reranker and safe_pool:
        from app.services.reranker_service import rerank

        for kr in korean_chunks:
            kr_id = kr.get("chunk_id")
            kr_text = (kr.get("chunk") or "").strip()
            if not kr_id or not kr_text:
                continue

            # 비용 제어: 너무 큰 풀은 잘라서 rerank
            cand_size = min(len(safe_pool), max(top_k_per_korean * 8, 80))
            cands = safe_pool[:cand_size]

            try:
                reranked = rerank(query=kr_text, cands=cands, top_k=top_k_per_korean)
                result[kr_id] = reranked
            except Exception:
                # fallback: fusion_score / score 기준 정렬
                sorted_pool = sorted(
                    cands,
                    key=lambda x: float(x.get("re_score", x.get("fusion_score", x.get("score", 0.0))) or 0.0),
                    reverse=True,
                )
                result[kr_id] = sorted_pool[:top_k_per_korean]
        return result

    # reranker 미사용 fallback
    for kr in korean_chunks:
        kr_id = kr.get("chunk_id")
        if not kr_id:
            continue
        sorted_pool = sorted(
            safe_pool,
            key=lambda x: float(x.get("fusion_score", x.get("score", 0.0)) or 0.0),
            reverse=True,
        )
        result[kr_id] = sorted_pool[:top_k_per_korean]

    return result
