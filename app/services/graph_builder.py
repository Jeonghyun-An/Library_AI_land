# app/services/graph_builder.py
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.constitution_search_optimizer import ConstitutionSearchOptimizer
from app.services.graph_service import (
    connect_article_concept,
    connect_article_sequence,
    connect_compare_articles,
    connect_country_document,
    connect_document_article,
    is_graph_enabled,
    upsert_article,
    upsert_concept,
    upsert_country,
    upsert_document,
)


def _safe_get(obj: Any, key: str, default=None):
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_structure(obj: Any) -> Dict[str, Any]:
    structure = _safe_get(obj, "structure", {}) or {}
    if isinstance(structure, dict):
        return structure
    return {}


def _make_article_id(
    country_code: str,
    version: Optional[str],
    article_number: Optional[str],
    paragraph: Optional[str] = None,
    fallback_doc_id: Optional[str] = None,
    fallback_seq: Optional[int] = None,
) -> str:
    v = (version or "latest").strip()
    a = str(article_number).strip() if article_number is not None else "unknown"

    if paragraph:
        p = str(paragraph).strip()
        return f"{country_code}:{v}:{a}:{p}"

    if article_number is not None:
        return f"{country_code}:{v}:{a}"

    if fallback_doc_id is not None and fallback_seq is not None:
        return f"{country_code}:{v}:{fallback_doc_id}:{fallback_seq}"

    return f"{country_code}:{v}:unknown"


def _extract_article_number(structure: Dict[str, Any]) -> Optional[str]:
    article_number = structure.get("article_number")
    if article_number is None:
        return None
    return str(article_number)


def _extract_paragraph(structure: Dict[str, Any]) -> Optional[str]:
    paragraph = structure.get("paragraph")
    if paragraph is None:
        return None
    return str(paragraph)


def _extract_concepts_from_text(text: str) -> List[Tuple[str, str]]:
    optimizer = ConstitutionSearchOptimizer()
    found: List[Tuple[str, str]] = []

    lowered = text.lower()

    for concept_name, keywords in optimizer.concept_keywords.items():
        for kw in keywords:
            if kw and kw.lower() in lowered:
                concept_key = f"ko:{concept_name}"
                found.append((concept_key, concept_name))
                break

    # 중복 제거
    unique = {}
    for key, name in found:
        unique[key] = name

    max_concepts = int(os.getenv("GRAPH_CONCEPT_MAX_PER_ARTICLE", "10"))
    return list(unique.items())[:max_concepts]


def build_constitution_graph(
    *,
    doc_id: str,
    country_code: str,
    country_name_ko: str,
    country_name_en: str,
    continent: str,
    region: str,
    title: str,
    version: Optional[str],
    is_bilingual: bool,
    minio_key: str,
    chunks: List[Any],
):
    if not is_graph_enabled():
        return

    # 1. Country / Document
    upsert_country({
        "code": country_code,
        "name_ko": country_name_ko,
        "name_en": country_name_en,
        "continent": continent,
        "region": region,
    })

    upsert_document({
        "doc_id": doc_id,
        "title": title,
        "version": version or "latest",
        "country_code": country_code,
        "country_name_ko": country_name_ko,
        "country_name_en": country_name_en,
        "continent": continent,
        "region": region,
        "is_bilingual": bool(is_bilingual),
        "minio_key": minio_key,
        "doc_type": "constitution",
    })

    connect_country_document(country_code, doc_id)

    # 2. Article nodes
    ordered_articles: List[Tuple[int, str]] = []

    for seq, chunk in enumerate(chunks):
        structure = _extract_structure(chunk)

        article_number = _extract_article_number(structure)
        paragraph = _extract_paragraph(structure)

        article_id = _make_article_id(
            country_code=country_code,
            version=version,
            article_number=article_number,
            paragraph=paragraph,
            fallback_doc_id=doc_id,
            fallback_seq=seq,
        )

        display_path = _safe_get(chunk, "display_path", "")
        text_ko = _normalize_text(_safe_get(chunk, "korean_text", ""))
        text_en = _normalize_text(_safe_get(chunk, "english_text", ""))
        search_text = _normalize_text(_safe_get(chunk, "search_text", ""))
        text_for_concept = text_ko or text_en or search_text

        page = _safe_get(chunk, "page", None)
        page_ko = _safe_get(chunk, "page_korean", None)
        page_en = _safe_get(chunk, "page_english", None)

        upsert_article({
            "article_id": article_id,
            "doc_id": doc_id,
            "country_code": country_code,
            "country_name": country_name_ko,
            "article_number": article_number,
            "paragraph": paragraph,
            "display_path": display_path,
            "text_ko": text_ko,
            "text_en": text_en,
            "search_text": search_text,
            "page": page,
            "page_korean": page_ko,
            "page_english": page_en,
            "doc_version": version or "latest",
            "constitution_title": title,
            "minio_key": minio_key,
            "seq": seq,
        })

        connect_document_article(doc_id, article_id)

        # sequence용 정렬 키
        if article_number and article_number.isdigit():
            ordered_articles.append((int(article_number), article_id))
        else:
            ordered_articles.append((100000 + seq, article_id))

        # concept edges
        concepts = _extract_concepts_from_text(text_for_concept)
        for concept_key, concept_name in concepts:
            upsert_concept(
                concept_key=concept_key,
                name=concept_name,
                lang="ko",
                normalized_name=concept_name.lower(),
            )
            connect_article_concept(article_id, concept_key, score=1.0)

    # 3. next/prev article edges
    ordered_articles.sort(key=lambda x: x[0])
    for i in range(len(ordered_articles) - 1):
        _, current_id = ordered_articles[i]
        _, next_id = ordered_articles[i + 1]
        connect_article_sequence(current_id, next_id)


def save_comparative_pairs_to_graph(
    *,
    query: str,
    pairs: List[Any],
):
    if not is_graph_enabled():
        return

    top_n_per_country = int(os.getenv("GRAPH_COMPARE_TOP_N_PER_COUNTRY", "3"))

    for pair in pairs or []:
        korean = getattr(pair, "korean", None)
        foreign = getattr(pair, "foreign", {}) or {}

        if korean is None:
            continue

        kr_structure = getattr(korean, "structure", {}) or {}
        kr_country = getattr(korean, "country", "KR")
        kr_article_number = kr_structure.get("article_number")
        kr_paragraph = kr_structure.get("paragraph")
        kr_version = kr_structure.get("constitution_version") or "latest"

        kr_article_id = _make_article_id(
            country_code=kr_country,
            version=kr_version,
            article_number=kr_article_number,
            paragraph=kr_paragraph,
            fallback_doc_id=kr_structure.get("doc_id"),
            fallback_seq=0,
        )

        for country_code, paged_result in foreign.items():
            items = getattr(paged_result, "items", []) or []

            for fx in items[:top_n_per_country]:
                fx_structure = getattr(fx, "structure", {}) or {}
                fx_country = getattr(fx, "country", country_code)
                fx_article_number = fx_structure.get("article_number")
                fx_paragraph = fx_structure.get("paragraph")
                fx_version = fx_structure.get("constitution_version") or "latest"

                fx_article_id = _make_article_id(
                    country_code=fx_country,
                    version=fx_version,
                    article_number=fx_article_number,
                    paragraph=fx_paragraph,
                    fallback_doc_id=fx_structure.get("doc_id"),
                    fallback_seq=0,
                )

                score = float(getattr(fx, "score", 0.0) or 0.0)

                connect_compare_articles(
                    source_article_id=kr_article_id,
                    target_article_id=fx_article_id,
                    score=score,
                    query_text=query,
                    relation_type="COMPARES_TO",
                )