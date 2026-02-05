# app/services/hybrid_search_service.py
"""
하이브리드 검색 서비스 (기존 reranker_service.py 호환)
- Dense(벡터) + Sparse(BM25) + Keyword(조항번호) 통합
- RRF (Reciprocal Rank Fusion) 스코어 통합
- 기존 reranker_service.rerank() 함수 사용
"""

import re
import math
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict


class BM25:
    """BM25 알고리즘 (Sparse Search)"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.avgdl = 0
        self.idf = {}
        self.doc_len = []
    
    def fit(self, corpus: List[str]):
        """문서 컬렉션으로 BM25 파라미터 학습"""
        self.doc_len = [len(doc.split()) for doc in corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        
        df = defaultdict(int)
        for doc in corpus:
            words = set(doc.lower().split())
            for word in words:
                df[word] += 1
        
        num_docs = len(corpus)
        for word, freq in df.items():
            self.idf[word] = math.log((num_docs - freq + 0.5) / (freq + 0.5) + 1)
    
    def score(self, query: str, doc_idx: int, doc_text: str) -> float:
        """쿼리와 문서 간 BM25 점수 계산"""
        if doc_idx >= len(self.doc_len):
            return 0.0
        
        score = 0.0
        doc_len = self.doc_len[doc_idx]
        query_terms = query.lower().split()
        doc_terms = doc_text.lower().split()
        doc_term_freqs = Counter(doc_terms)
        
        for term in query_terms:
            if term not in self.idf:
                continue
            
            tf = doc_term_freqs.get(term, 0)
            idf = self.idf[term]
            
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl))
            score += idf * (numerator / denominator)
        
        return score


def extract_article_numbers(query: str) -> List[str]:
    """쿼리에서 조항 번호 추출"""
    article_numbers = []
    
    # 한글: 제N조
    ko_matches = re.findall(r'제\s*(\d+)\s*조', query)
    article_numbers.extend(ko_matches)
    
    # 영문: Article N
    en_matches = re.findall(r'Article\s+\(?\s*(\d+)\s*\)?', query, re.IGNORECASE)
    article_numbers.extend(en_matches)
    
    return list(set(article_numbers))


def rrf_fusion(
    dense_results: List[Dict],
    sparse_results: List[Dict],
    keyword_results: List[Dict],
    dense_weight: float = 0.5,
    sparse_weight: float = 0.3,
    keyword_weight: float = 0.2,
    k: int = 60
) -> List[Dict]:
    """
    RRF (Reciprocal Rank Fusion)로 결과 통합
    """
    # 가중치 정규화
    total_weight = dense_weight + sparse_weight + keyword_weight
    dense_weight /= total_weight
    sparse_weight /= total_weight
    keyword_weight /= total_weight
    
    # chunk_id -> result 매핑
    fused_scores = {}
    
    # Dense 결과 처리
    for rank, result in enumerate(dense_results):
        chunk_id = result.get('chunk_id') or result.get('doc_id')
        rrf_score = 1.0 / (k + rank + 1)
        
        if chunk_id not in fused_scores:
            fused_scores[chunk_id] = {
                **result,
                'fusion_score': 0.0,
                'dense_rank': rank + 1,
                'sparse_rank': None,
                'keyword_rank': None
            }
        
        fused_scores[chunk_id]['fusion_score'] += dense_weight * rrf_score
    
    # Sparse 결과 처리
    for rank, result in enumerate(sparse_results):
        chunk_id = result.get('chunk_id') or result.get('doc_id')
        rrf_score = 1.0 / (k + rank + 1)
        
        if chunk_id not in fused_scores:
            fused_scores[chunk_id] = {
                **result,
                'fusion_score': 0.0,
                'dense_rank': None,
                'sparse_rank': rank + 1,
                'keyword_rank': None
            }
        
        fused_scores[chunk_id]['fusion_score'] += sparse_weight * rrf_score
        fused_scores[chunk_id]['sparse_rank'] = rank + 1
    
    # Keyword 결과 처리
    for rank, result in enumerate(keyword_results):
        chunk_id = result.get('chunk_id') or result.get('doc_id')
        rrf_score = 1.0 / (k + rank + 1)
        
        if chunk_id not in fused_scores:
            fused_scores[chunk_id] = {
                **result,
                'fusion_score': 0.0,
                'dense_rank': None,
                'sparse_rank': None,
                'keyword_rank': rank + 1
            }
        
        fused_scores[chunk_id]['fusion_score'] += keyword_weight * rrf_score
        fused_scores[chunk_id]['keyword_rank'] = rank + 1
    
    # 융합 점수로 정렬
    fused_results = sorted(fused_scores.values(), key=lambda x: x['fusion_score'], reverse=True)
    
    return fused_results


def hybrid_search(
    query: str,
    collection,
    embedding_model,
    top_k: int = 10,
    initial_retrieve: int = 100,
    country_filter: Optional[str] = None,
    dense_weight: float = 0.5,
    sparse_weight: float = 0.3,
    keyword_weight: float = 0.2,
    use_reranker: bool = True
) -> List[Dict]:
    """
    하이브리드 검색 실행
    
    Args:
        query: 검색 쿼리
        collection: Milvus 컬렉션
        embedding_model: 임베딩 모델
        top_k: 최종 반환 개수
        initial_retrieve: 초기 검색량
        country_filter: 국가 필터 (예: "KR")
        dense_weight: Dense 가중치
        sparse_weight: Sparse 가중치
        keyword_weight: Keyword 가중치
        use_reranker: 리랭커 사용 여부
    
    Returns:
        통합 검색 결과 (reranker 적용 완료)
    """
    print(f"[HYBRID-SEARCH] Query: '{query[:50]}...', country_filter={country_filter}")
    
    # 1. Dense Search (벡터 검색)
    query_embedding = embedding_model.encode([query], normalize_embeddings=True)[0]
    
    search_params = {"metric_type": "IP", "params": {"ef": 256}}
    
    # 국가 필터 표현식
    if country_filter:
        expr = f'metadata["country"] == "{country_filter}"'
    else:
        expr = None
    
    dense_results = collection.search(
        data=[query_embedding.tolist()],
        anns_field="embedding",
        param=search_params,
        limit=initial_retrieve,
        expr=expr,
        output_fields=["doc_id", "chunk_text", "metadata"]
    )
    
    dense_list = []
    for hits in dense_results:
        for rank, hit in enumerate(hits):
            dense_list.append({
                'chunk_id': hit.entity.get("doc_id"),
                'chunk': hit.entity.get("chunk_text"),  # ✅ reranker 호환
                'score': float(hit.score),
                'metadata': hit.entity.get("metadata"),
                'rank': rank + 1
            })
    
    print(f"[HYBRID-SEARCH] Dense: {len(dense_list)} results")
    
    # 2. Sparse Search (BM25)
    query_result = collection.query(
        expr=expr or "",
        output_fields=["doc_id", "chunk_text", "metadata"],
        limit=min(1000, initial_retrieve * 3)
    )
    
    if query_result:
        bm25 = BM25()
        corpus = [doc.get("chunk_text", "") for doc in query_result]
        bm25.fit(corpus)
        
        sparse_scores = []
        for idx, doc in enumerate(query_result):
            text = doc.get("chunk_text", "")
            score = bm25.score(query, idx, text)
            sparse_scores.append((idx, score, doc))
        
        sparse_scores.sort(key=lambda x: x[1], reverse=True)
        
        sparse_list = []
        for rank, (idx, score, doc) in enumerate(sparse_scores[:initial_retrieve]):
            sparse_list.append({
                'chunk_id': doc.get("doc_id"),
                'chunk': doc.get("chunk_text"),  # ✅ reranker 호환
                'score': score,
                'metadata': doc.get("metadata"),
                'rank': rank + 1
            })
        
        print(f"[HYBRID-SEARCH] Sparse: {len(sparse_list)} results")
    else:
        sparse_list = []
    
    # 3. Keyword Search (조항 번호)
    article_numbers = extract_article_numbers(query)
    keyword_list = []
    
    if article_numbers:
        print(f"[HYBRID-SEARCH] Found article numbers: {article_numbers}")
        
        for article_num in article_numbers:
            # metadata 구조에 맞게 수정
            expr_parts = [f'metadata["structure"]["article_number"] == "{article_num}"']
            if country_filter:
                expr_parts.append(f'metadata["country"] == "{country_filter}"')
            
            keyword_expr = " && ".join(expr_parts)
            
            try:
                keyword_results = collection.query(
                    expr=keyword_expr,
                    output_fields=["doc_id", "chunk_text", "metadata"],
                    limit=10
                )
                
                for rank, doc in enumerate(keyword_results):
                    keyword_list.append({
                        'chunk_id': doc.get("doc_id"),
                        'chunk': doc.get("chunk_text"),  # ✅ reranker 호환
                        'score': 10.0,
                        'metadata': doc.get("metadata"),
                        'rank': rank + 1
                    })
            except Exception as e:
                print(f"[HYBRID-SEARCH] Keyword search failed: {e}")
        
        print(f"[HYBRID-SEARCH] Keyword: {len(keyword_list)} results")
    
    # 4. RRF Fusion
    fused_results = rrf_fusion(
        dense_results=dense_list,
        sparse_results=sparse_list,
        keyword_results=keyword_list,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
        keyword_weight=keyword_weight
    )
    
    print(f"[HYBRID-SEARCH] Fused: {len(fused_results)} results")
    
    # 5. Reranking (기존 reranker_service.py 사용)
    if use_reranker and len(fused_results) > 0:
        try:
            from app.services.reranker_service import rerank
            
            # rerank() 함수는 {'chunk': str, 'score': float, 'metadata': dict} 형태 기대
            reranked = rerank(
                query=query,
                cands=fused_results[:min(len(fused_results), top_k * 3)],
                top_k=top_k
            )
            
            print(f"[HYBRID-SEARCH] Reranked: {len(reranked)} results")
            return reranked
        
        except Exception as e:
            print(f"[HYBRID-SEARCH] Reranking failed: {e}")
            # Reranker 실패 시 융합 결과 반환
            return fused_results[:top_k]
    
    return fused_results[:top_k]