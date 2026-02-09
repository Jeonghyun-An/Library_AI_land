# app/main.py
"""
도서관 지식검색 RAG 시스템 - FastAPI 메인 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import time

# 라우터 임포트
from app.api.library_router import router as library_router
from app.api.comparative_constitution_router import router as comparative_constitution_router

# FastAPI 앱 생성
app = FastAPI(
    title="Library Knowledge RAG API",
    description="도서관 지식검색을 위한 RAG 시스템",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영환경에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(library_router)
app.include_router(comparative_constitution_router)

# 루트 엔드포인트
@app.get("/")
async def root():
    return {
        "service": "Library Knowledge RAG System",
        "version": "1.0.0",
        "status": "running"
    }

# 헬스 체크
@app.get("/health")
async def health():
    return {"status": "healthy"}

# 시작 이벤트
@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작시 초기화"""
    start_time = time.time()
    
    print("=" * 80)
    print("Library Knowledge RAG System Starting...")
    print("=" * 80)
    
    # 1. MinIO 버킷 확인 및 생성
    print("\n[1/4] MinIO 초기화...")
    try:
        from app.services.minio_service import get_minio_client
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            print(f"  ✓ Created MinIO bucket: {bucket_name}")
        else:
            print(f"  ✓ MinIO bucket exists: {bucket_name}")
            
        # 필요한 폴더 생성
        for folder in ["metadata/", "books/", "temp/", "constitutions/"]:
            try:
                from io import BytesIO
                minio_client.put_object(
                    bucket_name,
                    folder,
                    BytesIO(b''),
                    0
                )
            except:
                pass
                
    except Exception as e:
        print(f"  ✗ MinIO initialization error: {e}")
    
    # 2. Milvus 연결 확인
    print("\n[2/4] Milvus 연결 확인...")
    try:
        from app.services.milvus_service import ensure_milvus_connected
        ensure_milvus_connected()
        print("✓ Milvus connection check OK")
    except Exception as e:
        print(f"Milvus not ready yet (will retry on demand): {e}")
    
    # 3. Embedding 모델 로드
    print("\n[3/4] Embedding 모델 로딩...")
    try:
        from app.services.embedding_model import get_embedding_model
        emb_model = get_embedding_model()
        model_name = os.getenv('EMBEDDING_MODEL_NAME', 'BAAI/bge-m3')
        dim = emb_model.get_sentence_embedding_dimension()
        print(f"  ✓ Embedding model loaded: {model_name} ({dim}차원)")
        
    except Exception as e:
        print(f"  ✗ Embedding model load error: {e}")
    
    # 4. Reranker 모델 로드 (preload_reranker 사용)
    print("\n[4/4] Reranker 모델 로딩...")
    try:
        from app.services.reranker_service import preload_reranker
        preload_reranker()  # 이 함수가 내부에서 워밍업까지 해줌
        model_name = os.getenv('RERANKER_MODEL_NAME', 'BAAI/bge-reranker-v2-m3')
        print(f"  ✓ Reranker model ready: {model_name}")
        
    except Exception as e:
        print(f"  ✗ Reranker model load error: {e}")
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"System Ready! (초기화 시간: {elapsed:.2f}초)")
    print("=" * 80 + "\n")

# 종료 이벤트
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료시 정리"""
    print("\n" + "=" * 80)
    print("Shutting down Library Knowledge RAG System...")
    print("=" * 80)
    
    # Milvus 연결 해제
    try:
        from pymilvus import connections
        connections.disconnect("default")
        print("✓ Milvus disconnected")
    except:
        pass
    
    print("=" * 80)
    print("Shutdown complete")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "0") == "1"
    )