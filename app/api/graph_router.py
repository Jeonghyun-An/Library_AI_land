# app/api/graph_router.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.graph_service import (
    expand_from_article,
    get_article_graph,
    get_articles_by_concept,
    get_country_article_counts,
    is_graph_enabled,
)
from app.services.graph_rerank_service import _load_article_evidence

router = APIRouter(prefix="/api/graph", tags=["graph-search"])


class GraphExpandRequest(BaseModel):
    article_id: str = Field(..., description="확장 시작 article_id")
    depth: int = Field(1, ge=1, le=3)
    limit: int = Field(30, ge=1, le=100)


class GraphConceptResponse(BaseModel):
    concept_name: str
    article: Dict[str, Any]
    score: float

class GraphArticleEvidenceResponse(BaseModel):
    article_id: str
    article_ids: List[str] = Field(default_factory=list)
    concept_keys: List[str] = Field(default_factory=list)
    concept_names: List[str] = Field(default_factory=list)
    compare_targets: List[str] = Field(default_factory=list)
    neighbor_articles: List[str] = Field(default_factory=list)

@router.get("/health")
def graph_health():
    return {
        "success": True,
        "graph_enabled": is_graph_enabled(),
    }


@router.get("/article/{article_id}")
def read_article_graph(article_id: str):
    if not is_graph_enabled():
        raise HTTPException(503, "Graph 기능이 비활성화되어 있습니다.")

    result = get_article_graph(article_id)
    if not result:
        raise HTTPException(404, f"해당 article_id를 찾을 수 없습니다: {article_id}")

    return {
        "success": True,
        "data": result,
    }


@router.get("/concept/{concept_name}", response_model=List[GraphConceptResponse])
def read_articles_by_concept(
    concept_name: str,
    limit: int = Query(20, ge=1, le=100),
):
    if not is_graph_enabled():
        raise HTTPException(503, "Graph 기능이 비활성화되어 있습니다.")

    rows = get_articles_by_concept(concept_name, limit=limit)
    return [GraphConceptResponse(**row) for row in rows]


@router.post("/expand")
def expand_article_graph(request: GraphExpandRequest):
    if not is_graph_enabled():
        raise HTTPException(503, "Graph 기능이 비활성화되어 있습니다.")

    result = expand_from_article(
        article_id=request.article_id,
        depth=request.depth,
        limit=request.limit,
    )

    if not result:
        raise HTTPException(404, f"확장할 article_id를 찾을 수 없습니다: {request.article_id}")

    return {
        "success": True,
        "data": result,
    }


@router.get("/stats/countries")
def graph_country_stats():
    if not is_graph_enabled():
        raise HTTPException(503, "Graph 기능이 비활성화되어 있습니다.")

    rows = get_country_article_counts()
    return {
        "success": True,
        "items": rows,
    }
    
@router.get("/article/{article_id}/evidence")
def read_article_evidence(article_id: str):
    if not is_graph_enabled():
        raise HTTPException(503, "Graph 기능이 비활성화되어 있습니다.")

    ev = _load_article_evidence([article_id])
    return {
        "success": True,
        "data": {
            "article_id": article_id,
            "article_ids": ev.get("article_ids", []),
            "concept_keys": sorted(list(ev.get("concept_keys", set()))),
            "concept_names": sorted(list(ev.get("concept_names", set()))),
            "compare_targets": sorted(list(ev.get("compare_targets", set()))),
            "neighbor_articles": sorted(list(ev.get("neighbor_articles", set()))),
        }
    }