# app/services/milvus_service.py
import os
import time
from typing import Optional
from pymilvus import connections, Collection, utility

_milvus_connected = False

def _connect_with_retry(alias: str, host: str, port: int, timeout: int, retries: int, backoff: float):
    last_err = None
    for i in range(1, retries + 1):
        try:
            connections.connect(
                alias=alias,
                host=host,
                port=port,
                timeout=timeout,
            )
            return
        except Exception as e:
            last_err = e
            print(f"[MILVUS] connect retry {i}/{retries} failed: {e}")
            time.sleep(backoff * i)
    raise last_err  # type: ignore

def ensure_milvus_connected() -> None:
    """Milvus 연결을 보장 (lazy + retry)."""
    global _milvus_connected
    if _milvus_connected and connections.has_connection("default"):
        return

    host = os.getenv("MILVUS_HOST", "milvus")
    port = int(os.getenv("MILVUS_PORT", "19530"))

    timeout = int(os.getenv("MILVUS_CONNECT_TIMEOUT", "60"))
    retries = int(os.getenv("MILVUS_CONNECT_RETRIES", "10"))
    backoff = float(os.getenv("MILVUS_CONNECT_BACKOFF", "1.0"))

    _connect_with_retry("default", host, port, timeout, retries, backoff)
    _milvus_connected = True
    print(f"[MILVUS] Connected to {host}:{port}")

def get_milvus_client():
    """호환용: 기존 코드 유지하려면 이 함수는 connections를 리턴."""
    ensure_milvus_connected()
    return connections

def ensure_collection_exists(collection_name: str, dim: int = 1024) -> Collection:
    """컬렉션 존재 확인 및 생성 (연결 보장 후 수행)."""
    ensure_milvus_connected()

    from pymilvus import CollectionSchema, FieldSchema, DataType

    for i in range(1, 6):
        try:
            if utility.has_collection(collection_name):
                col = Collection(name=collection_name)
                return col
            break
        except Exception as e:
            print(f"[MILVUS] has_collection retry {i}/5 failed: {e}")
            time.sleep(1.0 * i)

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]

    schema = CollectionSchema(fields=fields, description=f"Collection: {collection_name}")
    collection = Collection(name=collection_name, schema=schema)

    try:
        index_params = {
            "metric_type": os.getenv("MILVUS_METRIC_TYPE", "IP"),
            "index_type": os.getenv("MILVUS_INDEX_TYPE", "HNSW"),
            "params": {
                "M": int(os.getenv("MILVUS_HNSW_M", "16")),
                "efConstruction": int(os.getenv("MILVUS_HNSW_EFCON", "200")),
            },
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        print(f"[MILVUS] Created collection+index: {collection_name}")
    except Exception as e:
        print(f"[MILVUS] create_index skipped/failed (non-fatal): {e}")

    return collection

_collection_cache: dict[str, Collection] = {}

def get_collection(collection_name: str, dim: int = 1024) -> Collection:
    """
    컬렉션을 캐시로 관리.
    - 없으면 생성
    - 있으면 재사용
    - load는 1회만 보장
    """
    if collection_name in _collection_cache:
        return _collection_cache[collection_name]

    from app.services.milvus_service import ensure_collection_exists  # 같은 파일이면 직접 호출
    col = ensure_collection_exists(collection_name, dim=dim)

    try:
        col.load()
    except Exception as e:
        print(f"[MILVUS] load failed (will retry on demand): {e}")

    _collection_cache[collection_name] = col
    return col