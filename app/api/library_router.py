# app/api/library_router.py
"""
도서관 지식검색 RAG API
- 도서 업로드 및 인덱싱
- 의미 기반 검색
- 챕터/섹션 구조 보존
"""
from __future__ import annotations
import os
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
import traceback

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 서비스 임포트
from app.services.milvus_service import get_milvus_client
from app.services.embedding_model import get_embedding_model
from app.services.file_parser import parse_pdf, parse_pdf_blocks
from app.services.chunkers.chunking_unified import build_chunks
from app.services.minio_service import get_minio_client

router = APIRouter(prefix="/api/library", tags=["library"])


# ==================== 요청/응답 모델 ====================

class BookMetadata(BaseModel):
    """도서 메타데이터"""
    title: str = Field(..., description="도서 제목")
    author: Optional[str] = Field(None, description="저자")
    isbn: Optional[str] = Field(None, description="ISBN")
    publisher: Optional[str] = Field(None, description="출판사")
    publication_year: Optional[int] = Field(None, description="출판년도")
    category: Optional[str] = Field(None, description="카테고리 (fiction, technical, academic, textbook)")
    language: Optional[str] = Field("ko", description="언어 (ko, en)")
    page_count: Optional[int] = Field(None, description="페이지 수")
    description: Optional[str] = Field(None, description="도서 설명")


class BookUploadResponse(BaseModel):
    """도서 업로드 응답"""
    success: bool
    doc_id: str
    message: str
    job_id: Optional[str] = None
    metadata: Optional[Dict] = None


class SearchRequest(BaseModel):
    """검색 요청"""
    query: str = Field(..., min_length=1, description="검색 질의")
    top_k: int = Field(5, ge=1, le=20, description="반환할 결과 수")
    filters: Optional[Dict[str, Any]] = Field(None, description="필터 (저자, 카테고리 등)")
    use_reranking: bool = Field(True, description="리랭킹 사용 여부")
    search_type: str = Field("hybrid", description="검색 타입 (vector, keyword, hybrid)")


class SearchResult(BaseModel):
    """검색 결과 단일 아이템"""
    chunk_text: str
    score: float
    metadata: Dict[str, Any]
    book_title: Optional[str] = None
    author: Optional[str] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None


class SearchResponse(BaseModel):
    """검색 응답"""
    success: bool
    query: str
    results: List[SearchResult]
    total_found: int
    search_time_ms: float


# ==================== 도서 업로드 엔드포인트 ====================

@router.post("/upload", response_model=BookUploadResponse)
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF 파일"),
    title: str = Form(..., description="도서 제목"),
    author: Optional[str] = Form(None, description="저자"),
    isbn: Optional[str] = Form(None, description="ISBN"),
    publisher: Optional[str] = Form(None, description="출판사"),
    publication_year: Optional[int] = Form(None, description="출판년도"),
    category: Optional[str] = Form("general", description="카테고리"),
    language: Optional[str] = Form("ko", description="언어"),
    description: Optional[str] = Form(None, description="도서 설명"),
):
    """
    도서 업로드 및 인덱싱
    
    - PDF 파일 업로드
    - 텍스트 추출 및 OCR
    - 도서 특화 청킹 (챕터/섹션 인식)
    - 임베딩 및 벡터 DB 저장
    """
    try:
        # 파일 확장자 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
        
        # 메타데이터 구성
        metadata = BookMetadata(
            title=title,
            author=author,
            isbn=isbn,
            publisher=publisher,
            publication_year=publication_year,
            category=category,
            language=language,
            description=description
        )
        
        # doc_id 생성 (ISBN 우선, 없으면 제목+저자 기반)
        if isbn:
            doc_id = f"book_{isbn}"
        else:
            import hashlib
            unique_str = f"{title}_{author or 'unknown'}_{datetime.now().isoformat()}"
            hash_suffix = hashlib.md5(unique_str.encode()).hexdigest()[:8]
            doc_id = f"book_{hash_suffix}"
        
        # 임시 파일 저장
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        try:
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            temp_file.close()
            
            # 백그라운드 작업으로 처리
            job_id = f"upload_{doc_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            background_tasks.add_task(
                process_book_upload,
                temp_file.name,
                doc_id,
                metadata.model_dump(),
                job_id
            )
            
            return BookUploadResponse(
                success=True,
                doc_id=doc_id,
                message=f"도서 업로드가 시작되었습니다. job_id: {job_id}",
                job_id=job_id,
                metadata=metadata.model_dump()
            )
            
        except Exception as e:
            # 임시 파일 정리
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY-UPLOAD] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"업로드 실패: {str(e)}")


async def process_book_upload(file_path: str, doc_id: str, metadata: Dict, job_id: str):
    """
    백그라운드 도서 처리 작업
    - 파싱, 청킹, 임베딩, 저장
    """
    try:
        print(f"[{job_id}] Processing book: {doc_id}")
        
        # 1. PDF 파싱
        print(f"[{job_id}] Step 1: Parsing PDF...")
        pages = parse_pdf(file_path, by_page=True)
        if not pages:
            raise RuntimeError("PDF에서 텍스트를 추출하지 못했습니다.")
        
        # 레이아웃 블록 추출
        blocks_by_page = parse_pdf_blocks(file_path)
        layout_map = {int(p): blks for p, blks in (blocks_by_page or [])}
        
        # 페이지 표준화
        pages_std = []
        for item in pages:
            if isinstance(item, tuple) and len(item) >= 2:
                p, t = item[0], item[1]
            elif isinstance(item, dict):
                p, t = item.get('page', 0), item.get('text', '')
            else:
                continue
            pages_std.append((int(p), str(t or '')))
        
        # 페이지 수 업데이트
        metadata['page_count'] = len(pages_std)
        
        print(f"[{job_id}] Extracted {len(pages_std)} pages")
        
        # 2. 도서 특화 청킹
        print(f"[{job_id}] Step 2: Chunking with book-specific strategy...")
        
        # 환경 변수로 도서 청커 활성화 여부 확인
        use_book_chunker = os.getenv("RAG_ENABLE_BOOK_CHUNKER", "1") == "1"
        
        if use_book_chunker:
            try:
                from app.services.chunkers.book_chunker import book_chunk_pages
                from app.services.embedding_model import get_embedding_model
                
                # 토큰 인코더 생성
                emb_model = get_embedding_model()
                tokenizer = getattr(emb_model, "tokenizer", None)
                
                def encoder_fn(text: str):
                    if tokenizer is None:
                        # 폴백: 단어 기반 추정
                        return text.split()
                    return tokenizer.encode(text, add_special_tokens=False)
                
                # 도서 청킹 실행
                target_tokens = int(os.getenv("RAG_BOOK_TARGET_TOKENS", "512"))
                overlap_tokens = int(os.getenv("RAG_OVERLAP_TOKENS", "64"))
                min_chunk_tokens = int(os.getenv("RAG_MIN_CHUNK_TOKENS", "100"))
                
                chunks = book_chunk_pages(
                    pages_std,
                    encoder_fn,
                    target_tokens=target_tokens,
                    overlap_tokens=overlap_tokens,
                    layout_blocks=layout_map,
                    min_chunk_tokens=min_chunk_tokens
                )
                
                print(f"[{job_id}] Book chunker: {len(chunks)} chunks")
                
            except Exception as e:
                print(f"[{job_id}] Book chunker error: {e}, falling back to unified chunker")
                chunks = build_chunks(pages_std, layout_map, job_id=job_id)
        else:
            # 통합 청커 사용
            chunks = build_chunks(pages_std, layout_map, job_id=job_id)
        
        if not chunks:
            raise RuntimeError("청킹 결과가 비어있습니다.")
        
        # 3. 메타데이터 보강
        print(f"[{job_id}] Step 3: Enriching metadata...")
        enriched_chunks = []
        for chunk_text, chunk_meta in chunks:
            enriched_meta = {
                **chunk_meta,
                'doc_id': doc_id,
                'book_title': metadata.get('title'),
                'author': metadata.get('author'),
                'isbn': metadata.get('isbn'),
                'category': metadata.get('category'),
                'language': metadata.get('language'),
                'upload_time': datetime.now().isoformat()
            }
            enriched_chunks.append((chunk_text, enriched_meta))
        
        # 4. 임베딩 생성
        print(f"[{job_id}] Step 4: Generating embeddings...")
        emb_model = get_embedding_model()
        
        texts = [chunk_text for chunk_text, _ in enriched_chunks]
        embeddings = emb_model.encode(
            texts,
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            show_progress_bar=True,
            normalize_embeddings=True
        )
        
        # 5. Milvus에 저장
        print(f"[{job_id}] Step 5: Storing in vector DB...")
        milvus_client = get_milvus_client()
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        
        # 컬렉션 존재 확인 및 생성
        from pymilvus import utility, Collection, CollectionSchema, FieldSchema, DataType
        
        if not utility.has_collection(collection_name):
            # 스키마 정의
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),  # BGE-M3
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            schema = CollectionSchema(fields=fields, description="Library books collection")
            collection = Collection(name=collection_name, schema=schema)
            
            # 인덱스 생성
            index_params = {
                "metric_type": "IP",
                "index_type": "HNSW",
                "params": {"M": 16, "efConstruction": 200}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            print(f"[{job_id}] Created collection: {collection_name}")
        else:
            collection = Collection(name=collection_name)
        
        # 데이터 삽입
        entities = [
            [enriched_meta['doc_id'] for _, enriched_meta in enriched_chunks],  # doc_id
            [chunk_text for chunk_text, _ in enriched_chunks],  # chunk_text
            embeddings.tolist(),  # embedding
            [enriched_meta for _, enriched_meta in enriched_chunks]  # metadata
        ]
        
        collection.insert(entities)
        collection.flush()
        
        print(f"[{job_id}] Inserted {len(enriched_chunks)} chunks into {collection_name}")
        
        # 6. MinIO에 메타데이터 저장
        print(f"[{job_id}] Step 6: Storing metadata...")
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        import json
        metadata_json = json.dumps({
            **metadata,
            'doc_id': doc_id,
            'chunk_count': len(enriched_chunks),
            'processing_time': datetime.now().isoformat(),
            'status': 'completed'
        }, ensure_ascii=False, indent=2)
        
        from io import BytesIO
        minio_client.put_object(
            bucket_name,
            f"metadata/{doc_id}.json",
            BytesIO(metadata_json.encode('utf-8')),
            len(metadata_json.encode('utf-8')),
            content_type='application/json'
        )
        
        print(f"[{job_id}] Processing completed successfully")
        
    except Exception as e:
        print(f"[{job_id}] Error: {e}")
        traceback.print_exc()
    finally:
        # 임시 파일 정리
        if os.path.exists(file_path):
            os.unlink(file_path)


# ==================== 검색 엔드포인트 ====================

@router.post("/search", response_model=SearchResponse)
async def search_books(request: SearchRequest):
    """
    도서 지식검색
    
    - 의미 기반 벡터 검색
    - 하이브리드 검색 (벡터 + 키워드)
    - 리랭킹 지원
    - 필터링 (저자, 카테고리 등)
    """
    import time
    start_time = time.time()
    
    try:
        # 1. 쿼리 임베딩 생성
        emb_model = get_embedding_model()
        query_embedding = emb_model.encode([request.query], normalize_embeddings=True)[0]
        
        # 2. Milvus 검색
        milvus_client = get_milvus_client()
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        
        from pymilvus import Collection
        collection = Collection(name=collection_name)
        collection.load()
        
        # 검색 파라미터
        search_params = {
            "metric_type": "IP",
            "params": {"ef": int(os.getenv("MILVUS_EF_SEARCH", "256"))}
        }
        
        # 필터 표현식 구성
        expr = None
        if request.filters:
            filter_conditions = []
            if 'author' in request.filters:
                filter_conditions.append(f'metadata["author"] == "{request.filters["author"]}"')
            if 'category' in request.filters:
                filter_conditions.append(f'metadata["category"] == "{request.filters["category"]}"')
            if 'language' in request.filters:
                filter_conditions.append(f'metadata["language"] == "{request.filters["language"]}"')
            
            if filter_conditions:
                expr = " and ".join(filter_conditions)
        
        # 벡터 검색 실행
        search_result = collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=request.top_k * 2 if request.use_reranking else request.top_k,
            expr=expr,
            output_fields=["doc_id", "chunk_text", "metadata"]
        )
        
        # 3. 결과 파싱
        results = []
        for hits in search_result:
            for hit in hits:
                metadata = hit.entity.get('metadata', {})
                results.append({
                    'chunk_text': hit.entity.get('chunk_text', ''),
                    'score': float(hit.score),
                    'metadata': metadata,
                    'book_title': metadata.get('book_title'),
                    'author': metadata.get('author'),
                    'chapter': metadata.get('chapter'),
                    'section': metadata.get('section_title'),
                    'page': metadata.get('page')
                })
        
        # 4. 리랭킹 (선택)
        if request.use_reranking and len(results) > 0:
            try:
                from FlagEmbedding import FlagReranker
                reranker = FlagReranker(
                    os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3"),
                    use_fp16=True
                )
                
                # 쿼리-문서 쌍 생성
                pairs = [[request.query, r['chunk_text']] for r in results]
                rerank_scores = reranker.compute_score(pairs, normalize=True)
                
                # 스코어 업데이트
                for i, score in enumerate(rerank_scores):
                    results[i]['score'] = float(score)
                
                # 재정렬 및 상위 k개만 선택
                results = sorted(results, key=lambda x: x['score'], reverse=True)[:request.top_k]
                
            except Exception as e:
                print(f"[LIBRARY-SEARCH] Reranking error: {e}")
                # 리랭킹 실패시 원본 결과 사용
                results = results[:request.top_k]
        
        # 5. 응답 생성
        search_time_ms = (time.time() - start_time) * 1000
        
        return SearchResponse(
            success=True,
            query=request.query,
            results=[SearchResult(**r) for r in results],
            total_found=len(results),
            search_time_ms=round(search_time_ms, 2)
        )
        
    except Exception as e:
        print(f"[LIBRARY-SEARCH] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


# ==================== 도서 정보 조회 ====================

@router.get("/books/{doc_id}")
async def get_book_info(doc_id: str):
    """도서 메타데이터 조회"""
    try:
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        # MinIO에서 메타데이터 가져오기
        try:
            response = minio_client.get_object(bucket_name, f"metadata/{doc_id}.json")
            import json
            metadata = json.loads(response.read().decode('utf-8'))
            return JSONResponse(content={"success": True, "data": metadata})
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"도서를 찾을 수 없습니다: {doc_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIBRARY-INFO] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/books")
async def list_books(
    category: Optional[str] = None,
    author: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
):
    """도서 목록 조회"""
    try:
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        # MinIO에서 모든 메타데이터 파일 나열
        objects = minio_client.list_objects(bucket_name, prefix="metadata/", recursive=True)
        
        import json
        books = []
        for obj in objects:
            if obj.object_name.endswith('.json'):
                try:
                    response = minio_client.get_object(bucket_name, obj.object_name)
                    metadata = json.loads(response.read().decode('utf-8'))
                    
                    # 필터링
                    if category and metadata.get('category') != category:
                        continue
                    if author and metadata.get('author') != author:
                        continue
                    
                    books.append(metadata)
                except:
                    continue
        
        # 페이지네이션
        total = len(books)
        books = books[offset:offset+limit]
        
        return JSONResponse(content={
            "success": True,
            "data": books,
            "total": total,
            "limit": limit,
            "offset": offset
        })
        
    except Exception as e:
        print(f"[LIBRARY-LIST] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 헬스 체크 ====================

@router.get("/health")
async def health_check():
    """서비스 상태 확인"""
    return {"status": "healthy", "service": "library-rag"}