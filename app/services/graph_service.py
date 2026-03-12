# app/services/graph_service.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

_driver = None
_constraints_ready = False


def is_graph_enabled() -> bool:
    return os.getenv("GRAPH_ENABLED", "1") == "1"


def get_graph_driver():
    global _driver

    if not is_graph_enabled():
        return None

    if _driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")

        _driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_pool_size=20,
        )

    return _driver


def close_graph_driver():
    global _driver
    if _driver is not None:
        try:
            _driver.close()
        except Exception:
            pass
        _driver = None


def ensure_graph_constraints():
    global _constraints_ready

    if not is_graph_enabled():
        return

    if _constraints_ready:
        return

    driver = get_graph_driver()
    if driver is None:
        return

    database = os.getenv("NEO4J_DATABASE", "neo4j")

    statements = [
        "CREATE CONSTRAINT country_code_unique IF NOT EXISTS FOR (c:Country) REQUIRE c.code IS UNIQUE",
        "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:ConstitutionDocument) REQUIRE d.doc_id IS UNIQUE",
        "CREATE CONSTRAINT article_id_unique IF NOT EXISTS FOR (a:Article) REQUIRE a.article_id IS UNIQUE",
        "CREATE CONSTRAINT concept_key_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.key IS UNIQUE",
        "CREATE INDEX article_country_idx IF NOT EXISTS FOR (a:Article) ON (a.country_code)",
        "CREATE INDEX article_number_idx IF NOT EXISTS FOR (a:Article) ON (a.article_number)",
        "CREATE INDEX concept_name_idx IF NOT EXISTS FOR (c:Concept) ON (c.name)",
    ]

    with driver.session(database=database) as session:
        for stmt in statements:
            session.run(stmt)

    _constraints_ready = True


def _clean_props(props: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    for k, v in (props or {}).items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        elif isinstance(v, list):
            clean_list = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, (str, int, float, bool)):
                    clean_list.append(item)
                else:
                    clean_list.append(str(item))
            out[k] = clean_list
        elif isinstance(v, dict):
            # Neo4j property는 중첩 dict를 직접 받지 않으므로 문자열화
            out[k] = str(v)
        else:
            out[k] = str(v)

    return out


def run_write(query: str, params: Optional[Dict[str, Any]] = None):
    if not is_graph_enabled():
        return

    ensure_graph_constraints()
    driver = get_graph_driver()
    if driver is None:
        return

    database = os.getenv("NEO4J_DATABASE", "neo4j")

    with driver.session(database=database) as session:
        session.run(query, params or {})


def run_read(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if not is_graph_enabled():
        return []

    ensure_graph_constraints()
    driver = get_graph_driver()
    if driver is None:
        return []

    database = os.getenv("NEO4J_DATABASE", "neo4j")

    with driver.session(database=database) as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


def upsert_country(country: Dict[str, Any]):
    if not is_graph_enabled():
        return

    props = _clean_props(country)

    query = """
    MERGE (c:Country {code: $code})
    SET c += $props
    """
    run_write(query, {"code": props["code"], "props": props})


def upsert_document(document: Dict[str, Any]):
    if not is_graph_enabled():
        return

    props = _clean_props(document)

    query = """
    MERGE (d:ConstitutionDocument {doc_id: $doc_id})
    SET d += $props
    """
    run_write(query, {"doc_id": props["doc_id"], "props": props})


def connect_country_document(country_code: str, doc_id: str):
    query = """
    MATCH (c:Country {code: $country_code})
    MATCH (d:ConstitutionDocument {doc_id: $doc_id})
    MERGE (c)-[:HAS_DOCUMENT]->(d)
    """
    run_write(query, {"country_code": country_code, "doc_id": doc_id})


def upsert_article(article: Dict[str, Any]):
    if not is_graph_enabled():
        return

    props = _clean_props(article)

    query = """
    MERGE (a:Article {article_id: $article_id})
    SET a += $props
    """
    run_write(query, {"article_id": props["article_id"], "props": props})


def connect_document_article(doc_id: str, article_id: str):
    query = """
    MATCH (d:ConstitutionDocument {doc_id: $doc_id})
    MATCH (a:Article {article_id: $article_id})
    MERGE (d)-[:HAS_ARTICLE]->(a)
    """
    run_write(query, {"doc_id": doc_id, "article_id": article_id})


def connect_article_sequence(prev_article_id: str, next_article_id: str):
    query = """
    MATCH (a1:Article {article_id: $prev_article_id})
    MATCH (a2:Article {article_id: $next_article_id})
    MERGE (a1)-[:NEXT_ARTICLE]->(a2)
    MERGE (a2)-[:PREV_ARTICLE]->(a1)
    """
    run_write(query, {
        "prev_article_id": prev_article_id,
        "next_article_id": next_article_id,
    })


def upsert_concept(concept_key: str, name: str, lang: str = "ko", normalized_name: Optional[str] = None):
    props = _clean_props({
        "key": concept_key,
        "name": name,
        "lang": lang,
        "normalized_name": normalized_name or name.lower(),
    })

    query = """
    MERGE (c:Concept {key: $key})
    SET c += $props
    """
    run_write(query, {"key": concept_key, "props": props})


def connect_article_concept(article_id: str, concept_key: str, score: float = 1.0):
    query = """
    MATCH (a:Article {article_id: $article_id})
    MATCH (c:Concept {key: $concept_key})
    MERGE (a)-[r:RELATES_TO_CONCEPT]->(c)
    SET r.score = $score
    """
    run_write(query, {
        "article_id": article_id,
        "concept_key": concept_key,
        "score": float(score),
    })


def connect_compare_articles(
    source_article_id: str,
    target_article_id: str,
    score: float,
    query_text: Optional[str] = None,
    relation_type: str = "COMPARES_TO",
):
    cypher = f"""
    MATCH (a1:Article {{article_id: $source_article_id}})
    MATCH (a2:Article {{article_id: $target_article_id}})
    MERGE (a1)-[r:{relation_type}]->(a2)
    SET r.score = $score,
        r.query = $query_text
    """

    run_write(cypher, {
        "source_article_id": source_article_id,
        "target_article_id": target_article_id,
        "score": float(score),
        "query_text": query_text,
    })


def get_article_graph(article_id: str) -> Dict[str, Any]:
    article_query = """
    MATCH (a:Article {article_id: $article_id})
    OPTIONAL MATCH (a)-[:RELATES_TO_CONCEPT]->(c:Concept)
    OPTIONAL MATCH (a)-[:COMPARES_TO]->(fx:Article)
    OPTIONAL MATCH (a)-[:NEXT_ARTICLE]->(n:Article)
    OPTIONAL MATCH (a)-[:PREV_ARTICLE]->(p:Article)
    RETURN
      a {
        .article_id, .doc_id, .country_code, .country_name, .article_number,
        .paragraph, .display_path, .text_ko, .text_en, .page, .doc_version,
        .constitution_title, .minio_key
      } AS article,
      collect(DISTINCT c {
        .key, .name, .lang, .normalized_name
      }) AS concepts,
      collect(DISTINCT fx {
        .article_id, .country_code, .country_name, .article_number,
        .display_path, .text_ko, .text_en, .page
      }) AS foreign_articles,
      collect(DISTINCT n {
        .article_id, .article_number, .display_path, .country_code
      }) AS next_articles,
      collect(DISTINCT p {
        .article_id, .article_number, .display_path, .country_code
      }) AS prev_articles
    """

    rows = run_read(article_query, {"article_id": article_id})
    if not rows:
        return {}

    return rows[0]


def get_articles_by_concept(concept_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    query = """
    MATCH (c:Concept)
    WHERE toLower(c.name) CONTAINS toLower($concept_name)
       OR toLower(c.normalized_name) CONTAINS toLower($concept_name)
    MATCH (a:Article)-[r:RELATES_TO_CONCEPT]->(c)
    RETURN
      c.name AS concept_name,
      a {
        .article_id, .country_code, .country_name, .article_number,
        .display_path, .text_ko, .text_en, .page, .constitution_title
      } AS article,
      r.score AS score
    ORDER BY score DESC, a.country_code ASC
    LIMIT $limit
    """
    return run_read(query, {"concept_name": concept_name, "limit": int(limit)})


def expand_from_article(article_id: str, depth: int = 1, limit: int = 30) -> Dict[str, Any]:
    depth = max(1, min(depth, 3))
    limit = max(1, min(limit, 100))

    query = f"""
    MATCH (a:Article {{article_id: $article_id}})
    OPTIONAL MATCH path=(a)-[*1..{depth}]-(n)
    WITH a, collect(DISTINCT n)[0..$limit] AS neighbors
    RETURN
      a {{
        .article_id, .country_code, .country_name, .article_number,
        .display_path, .text_ko, .text_en, .page
      }} AS center,
      [x IN neighbors WHERE x:Article | x {{
        .article_id, .country_code, .country_name, .article_number,
        .display_path, .text_ko, .text_en, .page
      }}] AS articles,
      [x IN neighbors WHERE x:Concept | x {{
        .key, .name, .lang, .normalized_name
      }}] AS concepts
    """
    rows = run_read(query, {"article_id": article_id, "limit": limit})
    if not rows:
        return {}
    return rows[0]


def get_country_article_counts() -> List[Dict[str, Any]]:
    query = """
    MATCH (c:Country)-[:HAS_DOCUMENT]->(:ConstitutionDocument)-[:HAS_ARTICLE]->(a:Article)
    RETURN c.code AS country_code, c.name_ko AS country_name, count(a) AS article_count
    ORDER BY article_count DESC, country_code ASC
    """
    return run_read(query)


def delete_document_graph(doc_id: str):
    query = """
    MATCH (d:ConstitutionDocument {doc_id: $doc_id})
    OPTIONAL MATCH (d)-[:HAS_ARTICLE]->(a:Article)
    DETACH DELETE d, a
    """
    run_write(query, {"doc_id": doc_id})