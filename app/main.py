# app/main.py
"""
도서관 지식검색 RAG 시스템 - FastAPI 메인 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os

# 라우터 임포트
from app.api.library_router import router as library_router
from app.api.constitution_router import router as constitution_router

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
app.include_router(constitution_router)

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
    print("=" * 80)
    print("Library Knowledge RAG System Starting...")
    print("=" * 80)
    
    # MinIO 버킷 확인 및 생성
    try:
        from app.services.minio_service import get_minio_client
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            print(f"✓ Created MinIO bucket: {bucket_name}")
        else:
            print(f"✓ MinIO bucket exists: {bucket_name}")
            
        # 필요한 폴더 생성
        for folder in ["metadata/", "books/", "temp/"]:
            try:
                # 빈 객체로 폴더 생성 (MinIO는 폴더 개념이 없지만 prefix로 동작)
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
        print(f"✗ MinIO initialization error: {e}")
    
    try:
        from app.services.milvus_service import ensure_milvus_connected
        ensure_milvus_connected()
        print("✓ Milvus connection check OK")
    except Exception as e:
        print(f"Milvus not ready yet (will retry on demand): {e}")
    
    # 임베딩 모델 로드
    try:
        from app.services.embedding_model import get_embedding_model
        emb_model = get_embedding_model()
        print(f"✓ Embedding model loaded: {os.getenv('EMBEDDING_MODEL_NAME', 'BAAI/bge-m3')}")
    except Exception as e:
        print(f"✗ Embedding model load error: {e}")
    
    print("=" * 80)
    print("System Ready!")
    print("=" * 80)

# 종료 이벤트
@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료시 정리"""
    print("Shutting down Library Knowledge RAG System...")
    
    # Milvus 연결 해제
    try:
        from pymilvus import connections
        connections.disconnect("default")
        print("✓ Milvus disconnected")
    except:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "0") == "1"
    )