# app/services/hybrid_search_service.py
"""
하이브리드 검색 서비스 (FULL PATCH v2.0)
- Dense(벡터) + Sparse(BM25-like rank) + Keyword(조항번호) → RRF Fusion
- 점수 정규화: raw_score(원본) → score(실제 사용) → display_score(0~1 정규화)
- reranker 이후 score_threshold 적용
- Sparse corpus 범위 제한 + doc_type 필터
"""

from __future__ import annotations

import os
import re
import math
from typing import List, Dict, Any, Optional
from collections import defaultdict


# =========================
# Sparse (rank-only BM25)
# =========================
class BM25RankOnly:
    """
    BM25 rank-only implementation
    - raw score 폭주 방지
    - 순위 기반으로만 RRF에 반영
    """

    def fit(self, corpus: List[str]):
        # 확장 여지를 위한 메서드 (현재는 사용 안함)
        return

    def rank(self, query: str, corpus: List[str]) -> List[int]:
        """쿼리와 문서의 단어 overlap 기반 순위"""
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
    """조항 번호 추출 (한국어/영어)"""
    nums: List[str] = []
    # 한국어: 제57조, 제 10 조
    nums += re.findall(r"제\s*(\d+)\s*조", query)
    # 영어: Article 57, Article (10)
    nums += re.findall(r"Article\s*\(?\s*(\d+)\s*\)?", query, re.IGNORECASE)
    return list(set(nums))  # 중복 제거


def clamp01(x: float) -> float:
    """0~1 범위로 제한"""
    try:
        x = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, x))


def normalize_scores_minmax(scores: List[float]) -> List[float]:
    """Min-Max 정규화"""
    if not scores or len(scores) == 0:
        return []
    
    min_s = min(scores)
    max_s = max(scores)
    
    if max_s - min_s < 1e-9:
        # 모든 점수가 같으면 모두 1.0
        return [1.0] * len(scores)
    
    return [(s - min_s) / (max_s - min_s) for s in scores]


def normalize_scores_sigmoid(scores: List[float], scale: float = 1.0) -> List[float]:
    """Sigmoid 정규화 (0~1)"""
    if not scores:
        return []
    
    result = []
    for s in scores:
        try:
            sig = 1.0 / (1.0 + math.exp(-s * scale))
            result.append(sig)
        except (OverflowError, ZeroDivisionError):
            result.append(0.5)
    
    return result


def _ensure_meta_dict(meta: Any) -> Dict[str, Any]:
    """메타데이터를 dict로 변환"""
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


def _hit_field(hit: Any, field: str, default=None):
    """
    PyMilvus hit/entity 접근 호환 함수
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
    RRF(Reciprocal Rank Fusion)
    score = Σ weight * 1/(k + rank)
    
    Args:
        dense_results: 벡터 검색 결과
        sparse_results: BM25 검색 결과
        keyword_results: 키워드(조항번호) 검색 결과
        dense_weight: 벡터 가중치
        sparse_weight: BM25 가중치
        keyword_weight: 키워드 가중치
        k: RRF constant (default: 60)
    
    Returns:
        Fused results with fusion_score
    """
    # 가중치 정규화
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

    # Dense 추가
    for r, res in enumerate(dense_results or []):
        _add(r, res, dense_weight, "dense_rank")

    # Sparse 추가
    for r, res in enumerate(sparse_results or []):
        _add(r, res, sparse_weight, "sparse_rank")

    # Keyword 추가
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
    하이브리드 검색 메인 함수
    
    점수 체계:
    - raw_score: 원본 점수 (fusion_score or re_score)
    - score: 실제 사용 점수 (raw_score와 동일하지만 명시적)
    - display_score: 프론트엔드 표시용 (0~1 정규화)
    
    Args:
        query: 검색 쿼리
        collection: Milvus collection
        embedding_model: 임베딩 모델
        top_k: 반환할 결과 수
        initial_retrieve: 초기 검색 개수
        country_filter: 국가 필터 (예: "KR", "US")
        use_reranker: reranker 사용 여부
        score_threshold: 최소 점수 (reranker 이후 적용)
        min_results: 최소 결과 개수
        doc_type_filter: 문서 타입 필터
        sparse_corpus_limit: Sparse 검색 corpus 제한
        dense_weight, sparse_weight, keyword_weight: 각 검색 방식 가중치
    
    Returns:
        검색 결과 리스트 (각 항목은 raw_score, score, display_score 포함)
    """

    # ---------- 필터 expr 구성 ----------
    expr_parts: List[str] = []
    if doc_type_filter:
        expr_parts.append(f'metadata["doc_type"] == "{doc_type_filter}"')
    if country_filter:
        expr_parts.append(f'metadata["country"] == "{country_filter}"')

    expr = " && ".join(expr_parts) if expr_parts else None

    # ---------- Dense (벡터 검색) ----------
    q_emb = embedding_model.encode([query], normalize_embeddings=True)[0]

    METRIC = os.getenv("MILVUS_METRIC_TYPE", "IP")

    try:
        dense_hits = collection.search(
            data=[q_emb.tolist()],
            anns_field="embedding",
            param={"metric_type": METRIC, "params": {"ef": 250}},
            limit=initial_retrieve,
            expr=expr,
            output_fields=["doc_id", "chunk_text", "metadata"],
        )
    except Exception as e:
        print(f"[HYBRID] Dense search error: {e}")
        dense_hits = [[]]


    dense = []
    for hit in dense_hits[0]:
        doc_id_val = _hit_field(hit, "doc_id")
        chunk_val = _hit_field(hit, "chunk_text")
        meta_val = _hit_field(hit, "metadata")
        score_val = getattr(hit, "score", getattr(hit, "distance", 0.0))

        dense.append({
            "chunk_id": doc_id_val,
            "chunk": chunk_val,
            "score": float(score_val),  # 벡터 유사도 (내부용)
            "metadata": meta_val,
        })

    # ---------- Sparse (BM25 rank-only) ----------
    sparse = []
    try:
        # Corpus 가져오기 (제한)
        corpus_docs = collection.query(
            expr=expr,
            output_fields=["doc_id", "chunk_text", "metadata"],
            limit=sparse_corpus_limit,
        )

        if corpus_docs:
            corpus_texts = [d.get("chunk_text", "") for d in corpus_docs]
            bm25 = BM25RankOnly()
            bm25.fit(corpus_texts)
            ranked_indices = bm25.rank(query, corpus_texts)

            for rank_idx, doc_idx in enumerate(ranked_indices[:initial_retrieve]):
                doc = corpus_docs[doc_idx]
                sparse.append({
                    "chunk_id": doc.get("doc_id"),
                    "chunk": doc.get("chunk_text"),
                    "score": 1.0,  # rank-only, 점수는 RRF에서 계산
                    "metadata": doc.get("metadata"),
                    "rank": rank_idx + 1,
                })
    except Exception as e:
        print(f"[HYBRID] Sparse search error: {e}")

    # ---------- Keyword (조항번호) 검색 ----------
    keyword = []
    article_nums = extract_article_numbers(query)
    
    if article_nums:
        for num in article_nums:
            # 한국어 패턴
            kr_pattern = f'metadata["article_number"] == "{num}"'
            # 영어 패턴
            en_pattern = f'metadata["article_number"] == "{num}"'
            
            expr_kw_parts = []
            if doc_type_filter:
                expr_kw_parts.append(f'metadata["doc_type"] == "{doc_type_filter}"')
            if country_filter:
                expr_kw_parts.append(f'metadata["country"] == "{country_filter}"')
            
            # 조항번호 OR 조건
            expr_kw_parts.append(f'({kr_pattern} || {en_pattern})')
            
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
                keyword.append({
                    "chunk_id": doc.get("doc_id"),
                    "chunk": doc.get("chunk_text"),
                    "score": 1.0,  # 내부 참고용
                    "metadata": doc.get("metadata"),
                    "rank": r + 1,
                })

    # ---------- RRF Fusion ----------
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

        # reranker 후보 제한 (비용 절감)
        cand_size = min(len(fused), max(top_k * 4, 50))
        reranked = rerank(
            query=query,
            cands=fused[:cand_size],
            top_k=cand_size,
        )

    # ---------- Score Threshold (AFTER rerank) ----------
    if score_threshold is not None:
        passed = [
            r for r in reranked
            if float(r.get("re_score", r.get("fusion_score", 0.0)) or 0.0) >= score_threshold
        ]
        if len(passed) >= min_results:
            reranked = passed
        else:
            reranked = reranked[:min_results]

    # ---------- 점수 필드 정리 ----------
    # raw_score: 원본 (fusion_score or re_score)
    # score: 실제 사용 점수
    # display_score: 0~1 정규화 (프론트엔드용)
    
    # 1. raw_score 추출
    raw_scores = []
    for r in reranked:
        base = r.get("re_score", r.get("fusion_score", 0.0))
        r["raw_score"] = float(base or 0.0)
        raw_scores.append(r["raw_score"])
    
    # 2. display_score 정규화 (Min-Max)
    if raw_scores:
        normalized = normalize_scores_minmax(raw_scores)
        for i, r in enumerate(reranked):
            r["display_score"] = normalized[i]
            r["score"] = r["raw_score"]  # score는 raw_score와 동일
    else:
        for r in reranked:
            r["display_score"] = 0.0
            r["score"] = 0.0

    # metadata 정리
    for r in reranked:
        r["metadata"] = _ensure_meta_dict(r.get("metadata"))

    # top_k 제한
    if top_k and top_k > 0:
        return reranked[:top_k]
    return reranked


def match_foreign_to_korean(
    korean_chunks: List[Dict],
    foreign_pool: List[Dict],
    top_k_per_korean: int = 50,
    use_reranker: bool = True,
) -> Dict[str, List[Dict]]:
    """
    한국 조항별로 외국 조항 매칭
    
    Args:
        korean_chunks: 한국 조항 리스트
        foreign_pool: 외국 조항 풀
        top_k_per_korean: 한국 조항당 매칭할 외국 조항 수
        use_reranker: reranker 사용 여부
    
    Returns:
        {korean_chunk_id: [matched_foreign_chunks]}
    """
    from app.services.reranker_service import rerank
    
    matched = {}
    
    for kr_chunk in korean_chunks:
        kr_id = kr_chunk.get("chunk_id")
        kr_text = kr_chunk.get("chunk", "")
        
        if not kr_text or not foreign_pool:
            matched[kr_id] = []
            continue
        
        # reranker로 매칭
        if use_reranker:
            candidates = rerank(
                query=kr_text,
                cands=foreign_pool,
                top_k=top_k_per_korean,
            )
        else:
            # reranker 없이 fusion_score 기준
            candidates = sorted(
                foreign_pool,
                key=lambda x: x.get("fusion_score", 0.0),
                reverse=True
            )[:top_k_per_korean]
        
        # display_score 정규화
        raw_scores = [c.get("re_score", c.get("fusion_score", 0.0)) for c in candidates]
        normalized = normalize_scores_minmax(raw_scores)
        
        for i, c in enumerate(candidates):
            c["display_score"] = normalized[i]
            c["score"] = c.get("re_score", c.get("fusion_score", 0.0))
            c["raw_score"] = c["score"]
        
        matched[kr_id] = candidates
    
    return matched