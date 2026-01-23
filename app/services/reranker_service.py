# app/services/reranker_service.py
import os
import torch
from typing import Optional
from FlagEmbedding import FlagReranker

_reranker: Optional[FlagReranker] = None

def get_reranker() -> FlagReranker:
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
