# app/services/embedding_model.py
"""
임베딩 모델 서비스 (BGE-M3)
"""
import os
from typing import Optional
from sentence_transformers import SentenceTransformer

_embedding_model = None

def get_embedding_model():
    """임베딩 모델 싱글톤 (A4000 최적화)"""
    global _embedding_model
    
    if _embedding_model is None:
        model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
        device = "cuda" if os.getenv("CUDA_VISIBLE_DEVICES") else "cpu"
        
        try:
            print(f"[EMBEDDING] Loading model: {model_name} on {device}")
            _embedding_model = SentenceTransformer(
                model_name,
                device=device
            )
            
            # A4000 최적화: fp16 사용
            if device == "cuda":
                try:
                    import torch
                    _embedding_model = _embedding_model.half()
                    print("[EMBEDDING] Using FP16 for GPU optimization")
                except:
                    pass
            
            print(f"[EMBEDDING] Model loaded successfully")
            print(f"[EMBEDDING] Max sequence length: {_embedding_model.max_seq_length}")
            print(f"[EMBEDDING] Embedding dimension: {_embedding_model.get_sentence_embedding_dimension()}")
            
        except Exception as e:
            print(f"[EMBEDDING] Model load error: {e}")
            raise
    
    return _embedding_model