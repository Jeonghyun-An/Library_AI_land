# app/services/milvus_service.py
"""
Milvus 벡터 데이터베이스 서비스
"""
import os
from typing import Optional
from pymilvus import connections, Collection, utility

_milvus_client = None

def get_milvus_client():
    """Milvus 클라이언트 싱글톤"""
    global _milvus_client
    
    if _milvus_client is None:
        host = os.getenv("MILVUS_HOST", "localhost")
        port = int(os.getenv("MILVUS_PORT", "19530"))
        
        try:
            connections.connect(
                alias="default",
                host=host,
                port=port
            )
            print(f"[MILVUS] Connected to {host}:{port}")
            _milvus_client = connections
        except Exception as e:
            print(f"[MILVUS] Connection error: {e}")
            raise
    
    return _milvus_client


def ensure_collection_exists(collection_name: str, dim: int = 1024):
    """컬렉션 존재 확인 및 생성"""
    from pymilvus import CollectionSchema, FieldSchema, DataType
    
    if utility.has_collection(collection_name):
        return Collection(name=collection_name)
    
    # 스키마 정의
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]
    
    schema = CollectionSchema(fields=fields, description=f"Collection: {collection_name}")
    collection = Collection(name=collection_name, schema=schema)
    
    # 인덱스 생성
    index_params = {
        "metric_type": os.getenv("MILVUS_METRIC_TYPE", "IP"),
        "index_type": os.getenv("MILVUS_INDEX_TYPE", "HNSW"),
        "params": {
            "M": int(os.getenv("MILVUS_HNSW_M", "16")),
            "efConstruction": int(os.getenv("MILVUS_HNSW_EFCON", "200"))
        }
    }
    
    collection.create_index(field_name="embedding", index_params=index_params)
    print(f"[MILVUS] Created collection: {collection_name}")
    
    return collection