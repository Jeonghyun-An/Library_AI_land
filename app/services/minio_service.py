# app/services/minio_service.py
"""
MinIO 객체 저장소 서비스
"""
import os
from typing import Optional
from minio import Minio

_minio_client = None

def get_minio_client():
    """MinIO 클라이언트 싱글톤"""
    global _minio_client
    
    if _minio_client is None:
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        try:
            _minio_client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            print(f"[MINIO] Connected to {endpoint}")
        except Exception as e:
            print(f"[MINIO] Connection error: {e}")
            raise
    
    return _minio_client