# app/services/reranker_service.py
"""
리랭커 서비스 (BAAI/bge-reranker-v2-m3)
- FlagReranker 싱글톤 인스턴스 관리
- rerank 함수로 검색 결과 재정렬
"""
import os
import torch
from typing import Optional, List, Dict, Any
from FlagEmbedding import FlagReranker

_reranker: Optional[FlagReranker] = None

def get_reranker() -> FlagReranker:
    """
    리랭커 싱글톤 인스턴스 반환
    """
    global _reranker
    if _reranker is None:
        model_name = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # FlagReranker는 버전에 따라 device 인자 지원이 다를 수 있어 안전하게 try
        try:
            _reranker = FlagReranker(model_name, use_fp16=True, device=device)
        except TypeError:
            _reranker = FlagReranker(model_name, use_fp16=True)

        print(f"[RERANKER] loaded: {model_name} / device={device}")
    return _reranker


def rerank(
    query: str,
    cands: List[Dict[str, Any]],
    top_k: int = 5,
    batch_size: int = None
) -> List[Dict[str, Any]]:
    if not cands:
        return []
    
    if batch_size is None:
        batch_size = int(os.getenv("RERANKER_BATCH_SIZE", "64"))
    
    # 1. 리랭커 로드
    try:
        reranker = get_reranker()
    except Exception as e:
        print(f"[RERANK] Reranker load failed: {e}")
        # 리랭커 실패 시 원본 점수로 정렬
        sorted_cands = sorted(cands, key=lambda x: x.get('score', 0.0), reverse=True)
        for c in sorted_cands:
            c['re_score'] = c.get('score', 0.0)
            c['re_backend'] = 'fallback'
        return sorted_cands[:max(1, top_k)]
    
    # 2. 쿼리-문서 페어 생성
    pairs = []
    for cand in cands:
        chunk_text = cand.get('chunk', '')
        if not chunk_text:
            # chunk가 없으면 빈 문자열 (점수 낮게 나올 것)
            chunk_text = ""
        pairs.append([query, chunk_text])
    
    # 3. 리랭킹 점수 계산
    try:
        try:
            re_scores = reranker.compute_score(pairs, normalize=True, batch_size=batch_size)
        except TypeError:
            re_scores = reranker.compute_score(pairs, batch_size=batch_size)

        
        # 스칼라 값으로 변환 (리스트가 아닐 수도 있음)
        if not isinstance(re_scores, list):
            re_scores = [re_scores]
        
    except Exception as e:
        print(f"[RERANK] Scoring failed: {e}")
        import traceback
        traceback.print_exc()
        
        # 리랭킹 실패 시 원본 점수 사용
        sorted_cands = sorted(cands, key=lambda x: x.get('score', 0.0), reverse=True)
        for c in sorted_cands:
            c['re_score'] = c.get('score', 0.0)
            c['re_backend'] = 'fallback'
        return sorted_cands[:max(1, top_k)]
    
    # 4. re_score 필드 추가
    for cand, re_score in zip(cands, re_scores):
        cand['re_score'] = float(re_score)
        cand['re_backend'] = 'flag'
    
    # 5. re_score 기준 내림차순 정렬
    cands.sort(key=lambda x: x.get('re_score', -1e9), reverse=True)
    
    # 6. 상위 top_k개 반환
    result = cands[:max(1, top_k)]
    
    # 7. 로깅
    if result:
        top3_scores = [round(c.get('re_score', 0), 3) for c in result[:3]]
        print(f"[RERANK] Query='{query[:30]}...', top_k={top_k}, "
              f"total_cands={len(cands)}, top3_re_scores={top3_scores}")
    
    return result


def rerank_in_batches(
    query: str,
    cands: List[Dict[str, Any]],
    top_k: int = 5,
    batch_size: int = None,
) -> List[Dict[str, Any]]:
    """
    대량의 후보를 배치로 나누어 리랭킹
    
    Args:
        query: 검색 쿼리
        cands: 후보 청크 리스트
        top_k: 최종 반환할 상위 개수
        batch_size: 배치 크기 (None이면 환경변수 사용)
    
    Returns:
        리랭킹된 상위 top_k개
    """
    if not cands:
        return []

    if batch_size is None:
        batch_size = int(os.getenv("RERANKER_BATCH_SIZE", "64"))

    # 청크가 배치 크기보다 작으면 일반 리랭킹
    if len(cands) <= batch_size * 2:
        return rerank(query, cands, top_k)

    # 배치로 나누어 처리
    all_scored = []
    for i in range(0, len(cands), batch_size):
        batch = cands[i : i + batch_size]
        scored_batch = rerank(query, batch, top_k=len(batch))
        all_scored.extend(scored_batch)

    # 전체 재정렬
    all_scored.sort(key=lambda x: x.get("re_score", -1e9), reverse=True)

    return all_scored[:max(1, top_k)]


def preload_reranker():
    """
    앱 시작 시 리랭커 모델을 미리 로드
    첫 요청 시 발생하는 모델 로딩 지연 제거
    """
    print("[RERANK] Preloading reranker model...")
    
    try:
        reranker = get_reranker()
        
        # 테스트 스코어링으로 워밍업
        try:
            test_pairs = [["test query", "test document"]]
            _ = reranker.compute_score(test_pairs)
            print("[RERANK] Reranker warmed up successfully")
        except Exception as e:
            print(f"[RERANK] Warmup failed: {e}")
    
    except Exception as e:
        print(f"[RERANK] Preload failed: {e}")
    
    print("[RERANK] Reranker preload complete")