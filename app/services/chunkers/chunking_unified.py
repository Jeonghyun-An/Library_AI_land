# app/services/chunkers/chunking_unified.py
"""
통합 청킹 모듈 - 도서관 시스템용
도서 청커 우선, 폴백으로 기본 청커 사용
"""
from __future__ import annotations
import os
from typing import Dict, List, Tuple, Optional

def build_chunks(
    pages_std: List[Tuple[int, str]],
    layout_map: Optional[Dict[int, List[Dict]]] = None,
    *,
    job_id: Optional[str] = None
) -> List[Tuple[str, Dict]]:
    """
    통합 청킹 함수
    
    Args:
        pages_std: [(page_no, text), ...]
        layout_map: 레이아웃 정보
        job_id: 작업 ID (로깅용)
    
    Returns:
        [(chunk_text, metadata), ...]
    """
    layout_map = layout_map or {}
    
    # 인코더 생성
    enc, max_len = _make_encoder()
    
    # 환경 변수에서 파라미터 가져오기
    target_tokens = int(os.getenv("RAG_TARGET_TOKENS", "512"))
    overlap_tokens = int(os.getenv("RAG_OVERLAP_TOKENS", "64"))
    min_chunk_tokens = int(os.getenv("RAG_MIN_CHUNK_TOKENS", "100"))
    
    chunks = None
    
    # 1) 도서 청커 시도
    if os.getenv("RAG_ENABLE_BOOK_CHUNKER", "1") == "1":
        try:
            from app.services.chunkers.book_chunker import book_chunk_pages
            if job_id:
                print(f"[CHUNK-{job_id}] Trying book chunker...")
            
            chunks = book_chunk_pages(
                pages_std,
                enc,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
                layout_blocks=layout_map,
                min_chunk_tokens=min_chunk_tokens
            )
            
            if chunks and len(chunks) > 0:
                if job_id:
                    print(f"[CHUNK-{job_id}] Book chunker -> {len(chunks)} chunks")
                return chunks
            
            if job_id:
                print(f"[CHUNK-{job_id}] Book chunker returned empty, falling back")
        
        except Exception as e:
            if job_id:
                print(f"[CHUNK-{job_id}] Book chunker error: {e}")
    
    # 2) 기본 청커 폴백
    if job_id:
        print(f"[CHUNK-{job_id}] Using basic chunker...")
    
    chunks = _basic_chunk(pages_std, enc, target_tokens, overlap_tokens, min_chunk_tokens)
    
    if job_id:
        print(f"[CHUNK-{job_id}] Basic chunker -> {len(chunks)} chunks")
    
    return chunks


def _make_encoder():
    """토큰 인코더 생성"""
    from app.services.embedding_model import get_embedding_model
    
    model = get_embedding_model()
    tokenizer = getattr(model, "tokenizer", None)
    max_len = int(getattr(model, "max_seq_length", 512))
    
    def encoder(text: str):
        if tokenizer is None:
            # 폴백: 단어 기반
            return text.split()
        return tokenizer.encode(text, add_special_tokens=False) or []
    
    return encoder, max_len


def _basic_chunk(
    pages_std: List[Tuple[int, str]],
    encoder,
    target_tokens: int,
    overlap_tokens: int,
    min_chunk_tokens: int
) -> List[Tuple[str, Dict]]:
    """기본 토큰 기반 청킹"""
    import re
    
    chunks = []
    
    for page_no, text in pages_std:
        if not text or not text.strip():
            continue
        
        # 단락으로 분할
        paragraphs = re.split(r'\n\n+', text)
        
        current_chunk = ""
        current_tokens = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_tokens = len(encoder(para))
            
            if current_tokens + para_tokens <= target_tokens:
                current_chunk += "\n\n" + para if current_chunk else para
                current_tokens += para_tokens
            else:
                # 현재 청크 저장
                if current_chunk and current_tokens >= min_chunk_tokens:
                    chunks.append((
                        current_chunk.strip(),
                        {
                            'page': page_no,
                            'token_count': current_tokens,
                            'type': 'basic'
                        }
                    ))
                
                current_chunk = para
                current_tokens = para_tokens
        
        # 마지막 청크
        if current_chunk and current_tokens >= min_chunk_tokens:
            chunks.append((
                current_chunk.strip(),
                {
                    'page': page_no,
                    'token_count': current_tokens,
                    'type': 'basic'
                }
            ))
    
    return chunks