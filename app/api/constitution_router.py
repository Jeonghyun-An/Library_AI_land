# app/api/constitution_router.py
"""
헌법 전문 AI API 라우터 (LIBRARY 프로젝트용)
- library_router.py 스타일 참고
- RAG_LAND 로직 재사용
"""
from __future__ import annotations
import os
import hashlib
import time
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

# LIBRARY 프로젝트 기존 서비스 재사용
from app.services.embedding_model import get_embedding_model
from app.services.milvus_service import get_milvus_client
from app.services.minio_service import get_minio_client
from app.services.file_parser import parse_pdf

# 헌법 특화 모듈
from app.services.chunkers.constitution_chunker import (
    ConstitutionChunker,
    chunk_constitution_document
)
from app.services.constitution_search_optimizer import (
    ConstitutionSearchOptimizer,
    optimize_constitution_search,
    boost_constitution_results
)

router = APIRouter(prefix="/api/constitution", tags=["constitution"])


# ==================== 요청/응답 모델 ====================

class ConstitutionUploadRequest(BaseModel):
    """헌법 업로드 메타데이터"""
    title: str = Field(..., description="헌법 제목")
    version: Optional[str] = Field(None, description="개정 날짜 (YYYY-MM-DD)")
    language: str = Field("ko", description="언어 (ko | en)")
    description: Optional[str] = Field(None, description="설명")


class ConstitutionSearchRequest(BaseModel):
    """헌법 검색 요청"""
    query: str = Field(..., min_length=1, description="검색 질의")
    top_k: int = Field(5, ge=1, le=30, description="반환 결과 수")
    language: str = Field("ko", description="언어")
    use_reranking: bool = Field(True, description="리랭킹 사용")
    
    # 헌법 특화 필터
    article_filter: Optional[List[str]] = Field(None, description="조항 필터")
    chapter_filter: Optional[List[str]] = Field(None, description="장 필터")


class ConstitutionSearchResponse(BaseModel):
    """헌법 검색 응답"""
    query: str
    query_analysis: Dict[str, Any]
    results: List[Dict[str, Any]]
    total_found: int
    search_time_ms: float


# ==================== 업로드 엔드포인트 ====================

@router.post("/upload")
async def upload_constitution(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    background_tasks: BackgroundTasks = None
):
    """
    헌법 문서 업로드 (library_router.py 스타일)
    """
    import json
    import tempfile
    
    try:
        meta = json.loads(metadata)
        upload_meta = ConstitutionUploadRequest(**meta)
    except Exception as e:
        raise HTTPException(400, f"메타데이터 오류: {e}")
    
    # 임시 파일 저장
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # doc_id 생성
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        doc_id = f"constitution_{upload_meta.language}_{content_hash}"
        
        # 중복 체크 (Milvus)
        milvus_client = get_milvus_client()
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        
        # 백그라운드 인덱싱
        if background_tasks:
            background_tasks.add_task(
                _index_constitution_background,
                temp_file.name,
                doc_id,
                collection_name,
                upload_meta.dict()
            )
            
            return {
                "success": True,
                "message": "헌법 문서 인덱싱이 시작되었습니다.",
                "doc_id": doc_id,
                "status": "processing"
            }
        else:
            # 동기 처리
            await _index_constitution_background(
                temp_file.name,
                doc_id,
                collection_name,
                upload_meta.dict()
            )
            
            return {
                "success": True,
                "message": "헌법 문서 인덱싱이 완료되었습니다.",
                "doc_id": doc_id,
                "status": "completed"
            }
    
    finally:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


async def _index_constitution_background(
    file_path: str,
    doc_id: str,
    collection_name: str,
    metadata: Dict[str, Any]
):
    """헌법 인덱싱 백그라운드 작업 (library_router 스타일)"""
    import traceback
    
    try:
        print(f"[CONSTITUTION] Indexing started: {doc_id}")
        
        # 1. PDF 파싱
        pages = parse_pdf(file_path)
        print(f"[CONSTITUTION] Parsed {len(pages)} pages")
        
        # 2. 헌법 청킹
        chunker = ConstitutionChunker(
            target_tokens=512,
            overlap_tokens=64,
            enable_cross_page=True
        )
        
        chunks = chunker.chunk(
            pages=pages,
            doc_id=doc_id,
            lang=metadata.get('language', 'ko')
        )
        
        print(f"[CONSTITUTION] Generated {len(chunks)} chunks")
        
        # 3. 메타데이터 보강
        enriched_chunks = []
        for chunk_text, chunk_meta in chunks:
            chunk_meta.update({
                'constitution_title': metadata.get('title'),
                'constitution_version': metadata.get('version'),
                'language': metadata.get('language'),
                'indexed_at': datetime.utcnow().isoformat(),
            })
            enriched_chunks.append((chunk_text, chunk_meta))
        
        # 4. 임베딩 생성
        emb_model = get_embedding_model()
        texts = [chunk_text for chunk_text, _ in enriched_chunks]
        
        embeddings = emb_model.encode(
            texts,
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            show_progress_bar=True,
            normalize_embeddings=True
        )
        
        print(f"[CONSTITUTION] Generated embeddings: {embeddings.shape}")
        
        # 5. Milvus 저장 (library_router 스타일)
        milvus_client = get_milvus_client()
        from app.services.milvus_service import get_collection
        
        collection = get_collection(collection_name, dim=1024)
        
        entities = [
            [meta['doc_id'] for _, meta in enriched_chunks],
            [t for t, _ in enriched_chunks],
            embeddings.tolist(),
            [meta for _, meta in enriched_chunks],
        ]
        
        collection.insert(entities)
        collection.flush()
        
        print(f"[CONSTITUTION] Inserted {len(enriched_chunks)} chunks into Milvus")
        
        # 6. MinIO 메타데이터 저장
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        import json
        metadata_json = json.dumps({
            **metadata,
            'doc_id': doc_id,
            'chunk_count': len(enriched_chunks),
            'indexed_at': datetime.utcnow().isoformat(),
            'status': 'completed'
        }, ensure_ascii=False, indent=2)
        
        from io import BytesIO
        minio_client.put_object(
            bucket_name,
            f"constitution/{doc_id}.json",
            BytesIO(metadata_json.encode('utf-8')),
            len(metadata_json.encode('utf-8')),
            content_type='application/json'
        )
        
        print(f"[CONSTITUTION] Indexing completed: {doc_id}")
    
    except Exception as e:
        print(f"[CONSTITUTION] Indexing failed: {e}")
        traceback.print_exc()
        raise


# ==================== 검색 엔드포인트 ====================

@router.post("/search", response_model=ConstitutionSearchResponse)
async def search_constitution(request: ConstitutionSearchRequest):
    """
    헌법 조항 검색 (RAG_LAND 검색 로직 재사용)
    """
    start_time = time.time()
    
    try:
        # 1. 쿼리 최적화
        optimizer = ConstitutionSearchOptimizer()
        query_analysis = optimizer.optimize_query(request.query, request.language)
        
        print(f"[CONSTITUTION-SEARCH] Query analysis: {query_analysis}")
        
        # 2. 임베딩 생성
        emb_model = get_embedding_model()
        search_query = query_analysis['optimized_query']
        query_embedding = emb_model.encode([search_query], normalize_embeddings=True)[0]
        
        # 3. Milvus 검색 (library_router 스타일)
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        from app.services.milvus_service import get_collection
        
        collection = get_collection(collection_name, dim=1024)
        
        # 검색 파라미터
        search_params = {
            "metric_type": "IP",
            "params": {"ef": int(os.getenv("MILVUS_EF_SEARCH", "256"))}
        }
        
        # 초기 검색량 (RAG_LAND 스타일)
        initial_top_k = request.top_k * 8
        
        search_result = collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=initial_top_k,
            output_fields=["doc_id", "chunk_text", "metadata"]
        )
        
        # 4. 결과 파싱
        candidates = []
        for hits in search_result:
            for hit in hits:
                meta_raw = hit.entity.get('metadata', {})
                
                # metadata가 JSON 문자열일 수 있음
                if isinstance(meta_raw, str):
                    import json
                    meta = json.loads(meta_raw)
                else:
                    meta = meta_raw or {}
                
                candidates.append({
                    'chunk': hit.entity.get('chunk_text', ''),
                    'score': float(hit.score),
                    'metadata': meta
                })
        
        print(f"[CONSTITUTION-SEARCH] Initial results: {len(candidates)}")
        
        # 5. 조항/장 필터
        if request.article_filter or query_analysis.get('article_filters'):
            article_filters = set(request.article_filter or []) | set(query_analysis.get('article_filters', []))
            candidates = [
                c for c in candidates
                if str(c['metadata'].get('article_number', '')) in article_filters
            ]
        
        if request.chapter_filter or query_analysis.get('chapter_filters'):
            chapter_filters = set(request.chapter_filter or []) | set(query_analysis.get('chapter_filters', []))
            candidates = [
                c for c in candidates
                if str(c['metadata'].get('chapter_number', '')) in chapter_filters
            ]
        
        # 6. 헌법 부스팅 (RAG_LAND 스타일)
        boosted_results = optimizer.apply_constitution_boost(candidates, query_analysis)
        
        # 7. 리랭킹 (옵션)
        if request.use_reranking and len(boosted_results) > request.top_k:
            # RAG_LAND reranker 재사용 가능
            try:
                from app.services.reranker import rerank
                
                reranked = rerank(
                    query=request.query,
                    cands=boosted_results[:request.top_k * 2],
                    top_k=request.top_k
                )
                
                final_results = reranked
            except ImportError:
                # reranker 없으면 부스팅 결과 그대로
                final_results = boosted_results[:request.top_k]
        else:
            final_results = boosted_results[:request.top_k]
        
        # 8. 응답 구성
        search_time = (time.time() - start_time) * 1000
        
        return ConstitutionSearchResponse(
            query=request.query,
            query_analysis=query_analysis,
            results=final_results,
            total_found=len(candidates),
            search_time_ms=search_time
        )
    
    except Exception as e:
        raise HTTPException(500, f"검색 실패: {e}")


# ==================== 통계 엔드포인트 ====================

@router.get("/stats")
async def get_constitution_stats():
    """헌법 데이터 통계"""
    try:
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        from app.services.milvus_service import get_collection
        
        collection = get_collection(collection_name, dim=1024)
        
        # 전체 청크 수
        total_chunks = collection.num_entities
        
        return {
            "collection": collection_name,
            "total_chunks": total_chunks,
            "dimension": 1024,
            "status": "active"
        }
    
    except Exception as e:
        raise HTTPException(500, f"통계 조회 실패: {e}")