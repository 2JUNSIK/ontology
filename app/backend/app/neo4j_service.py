"""Neo4j 실행 계층 (M4).

관심사 분리(불변식 §2): Cypher '생성'은 cypher_builder(순수 함수), '실행'은 여기가 담당.
neo4j 파이썬 드라이버 **6.x** API 기준.

- 드라이버는 **지연 초기화 싱글턴**. 앱 종료 시 close_driver()로 정리(main.py lifespan).
- Neo4j 미가동/연결 불가는 ServiceUnavailable을 잡아 `Neo4jUnavailable`로 승격 →
  라우터가 503으로 변환한다(백엔드가 죽지 않고 우아하게 열화).
- **스키마 DDL(CREATE CONSTRAINT)** 은 auto-commit 트랜잭션(`session.run`)으로 실행한다.
  각 문이 개별 트랜잭션이라 한 트랜잭션 내 스키마/데이터 혼용 금지 규칙을 자연히 회피한다.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Any

import neo4j
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from .config import settings
from .cypher_builder import (
    ENTITY_BASE_LABEL,
    META_NODE_LABEL,
    META_REL_TYPE,
    build_commit_statements,
    build_entity_constraint,
    build_ingest_statements,
)
from .models import Extraction, OntologySchema

PROJECT_LABEL = "_Project"

logger = logging.getLogger(__name__)

_DATABASE = "neo4j"  # community 기본 데이터베이스
_driver: neo4j.Driver | None = None
_driver_lock = threading.Lock()  # FastAPI가 sync 엔드포인트를 스레드풀에서 실행 → 경합 방지


class Neo4jUnavailable(RuntimeError):
    """Neo4j 연결 불가. 라우터가 503으로 변환한다."""


def get_driver() -> neo4j.Driver:
    """지연 초기화 싱글턴 드라이버. 최초 호출 시 생성한다(이중 체크 잠금)."""
    global _driver
    if _driver is None:
        with _driver_lock:
            if _driver is None:  # 잠금 획득 사이에 다른 스레드가 만들었을 수 있음
                _driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
    return _driver


def close_driver() -> None:
    """앱 종료 시 드라이버 정리(main.py lifespan에서 호출)."""
    global _driver
    with _driver_lock:
        if _driver is not None:
            _driver.close()
            _driver = None


def _add_counters(agg: dict[str, int], counters: Any) -> None:
    """Neo4j SummaryCounters를 누적 dict에 더한다."""
    agg["nodes_created"] += counters.nodes_created
    agg["nodes_deleted"] += counters.nodes_deleted
    agg["relationships_created"] += counters.relationships_created
    agg["properties_set"] += counters.properties_set
    agg["constraints_added"] += counters.constraints_added


def _loads(value: Any) -> list[dict]:
    """properties_json 역직렬화. 손상/None이면 빈 목록으로 안전 처리."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def commit_schema(schema: OntologySchema) -> dict[str, Any]:
    """스키마를 Neo4j에 반영한다.

    트랜잭션 전략(원자성 vs 스키마/데이터 혼용 금지 규칙의 균형):
    - **제약 DDL**(constraint)은 각각 auto-commit(`session.run`)으로 실행한다. 한 트랜잭션에
      스키마 변경과 데이터 변경을 함께 둘 수 없다는 Neo4j 제약을 지키기 위함이며, DDL은
      IF NOT EXISTS로 멱등하다.
    - **메타 교체**(meta_clear→meta_node→meta_rel)는 전부 순수 데이터 연산이므로 **하나의
      관리형 쓰기 트랜잭션**(`execute_write`)으로 묶어 원자화한다. 이렇게 하면 초기화만
      되고 새 메타는 안 써지는 '부분 커밋' 창이 생기지 않는다(all-or-nothing).

    반환: {applied_cypher: [...], stats: {...}} (PLAN.md §5).
    """
    statements = build_commit_statements(schema)
    constraint_stmts = [s for s in statements if s.kind == "constraint"]
    data_stmts = [s for s in statements if s.kind != "constraint"]
    driver = get_driver()
    applied: list[str] = []
    counters = {
        "nodes_created": 0,
        "nodes_deleted": 0,
        "relationships_created": 0,
        "properties_set": 0,
        "constraints_added": 0,
    }

    def _write_meta(tx) -> list:
        # 관리형 트랜잭션 내부: 실패 시 전체 롤백된다(원자적 메타 교체).
        return [tx.run(st.cypher, st.params).consume().counters for st in data_stmts]

    try:
        with driver.session(database=_DATABASE) as session:
            # 1) 스키마 DDL — 개별 auto-commit
            for st in constraint_stmts:
                _add_counters(counters, session.run(st.cypher, st.params).consume().counters)
                applied.append(st.cypher)
            # 2) 메타 교체 — 단일 관리형 쓰기 트랜잭션(원자적)
            if data_stmts:
                for c in session.execute_write(_write_meta):
                    _add_counters(counters, c)
                applied.extend(st.cypher for st in data_stmts)
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(commit): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e

    return {
        "applied_cypher": applied,
        "stats": {
            "statements": len(applied),
            "constraints": len(constraint_stmts),
            "meta_nodes": len(schema.nodes),
            "meta_relationships": len(schema.relationships),
            "counters": counters,
        },
    }


def fetch_graph() -> dict[str, list[dict]]:
    """커밋된 스키마 메타 그래프를 시각화용 {nodes, links}로 조회(읽기 전용).

    노드 id는 라벨(고유). links의 source/target은 노드 id(라벨)와 매칭된다
    (react-force-graph 규약).
    """
    driver = get_driver()
    node_q = (
        f"MATCH (s:`{META_NODE_LABEL}`) "
        "RETURN s.label AS label, s.description AS description, "
        "s.key_property AS key_property, s.properties_json AS properties_json "
        "ORDER BY label"
    )
    rel_q = (
        f"MATCH (a:`{META_NODE_LABEL}`)-[r:`{META_REL_TYPE}`]->(b:`{META_NODE_LABEL}`) "
        "RETURN a.label AS source, b.label AS target, r.rel_type AS type, "
        "r.description AS description, r.properties_json AS properties_json "
        "ORDER BY type"
    )
    try:
        node_res = driver.execute_query(
            node_q, routing_=neo4j.RoutingControl.READ, database_=_DATABASE
        )
        rel_res = driver.execute_query(
            rel_q, routing_=neo4j.RoutingControl.READ, database_=_DATABASE
        )
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(graph): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e

    nodes = [
        {
            "id": r["label"],
            "label": r["label"],
            "description": r["description"] or "",
            "key_property": r["key_property"],
            "properties": _loads(r["properties_json"]),
        }
        for r in node_res.records
    ]
    links = [
        {
            "source": r["source"],
            "target": r["target"],
            "type": r["type"],
            "description": r["description"] or "",
            "properties": _loads(r["properties_json"]),
        }
        for r in rel_res.records
    ]
    return {"nodes": nodes, "links": links}


# ==================================================================
# v2: 프로젝트 & 지식그래프 (PLAN.md §5·§6)
# ==================================================================


def _ensure_entity_constraint(session) -> None:
    """엔티티 (_project,_name) UNIQUE 제약 보장(스키마 op, auto-commit). IF NOT EXISTS."""
    st = build_entity_constraint()
    session.run(st.cypher).consume()


def create_project(name: str, description: str = "") -> dict[str, Any]:
    """프로젝트 생성(+엔티티 제약 보장). id는 서버 생성 uuid."""
    pid = uuid.uuid4().hex
    driver = get_driver()
    try:
        with driver.session(database=_DATABASE) as session:
            _ensure_entity_constraint(session)  # 스키마 op 먼저(별도 트랜잭션)
            rec = session.run(
                f"MERGE (p:`{PROJECT_LABEL}` {{id: $id}}) "
                "SET p.name = $name, p.description = $description, "
                "p.created_ts = timestamp() "
                "RETURN p.id AS id, p.name AS name, p.description AS description, "
                "p.created_ts AS created_ts",
                {"id": pid, "name": name, "description": description},
            ).single()
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(create_project): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e
    return rec.data()


def list_projects() -> list[dict[str, Any]]:
    """프로젝트 목록(최신순)."""
    driver = get_driver()
    try:
        res = driver.execute_query(
            f"MATCH (p:`{PROJECT_LABEL}`) "
            "RETURN p.id AS id, p.name AS name, p.description AS description, "
            "p.created_ts AS created_ts "
            "ORDER BY p.created_ts DESC",
            routing_=neo4j.RoutingControl.READ,
            database_=_DATABASE,
        )
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(list_projects): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e
    return [r.data() for r in res.records]


def get_project(project_id: str) -> dict[str, Any] | None:
    """단일 프로젝트 조회(없으면 None)."""
    driver = get_driver()
    try:
        res = driver.execute_query(
            f"MATCH (p:`{PROJECT_LABEL}` {{id: $id}}) "
            "RETURN p.id AS id, p.name AS name, p.description AS description, "
            "p.created_ts AS created_ts",
            {"id": project_id},
            routing_=neo4j.RoutingControl.READ,
            database_=_DATABASE,
        )
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(get_project): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e
    return res.records[0].data() if res.records else None


def delete_project(project_id: str) -> dict[str, int]:
    """프로젝트와 그 프로젝트의 엔티티를 함께 삭제(원자적)."""
    driver = get_driver()
    try:
        with driver.session(database=_DATABASE) as session:
            def _del(tx):
                ents = (
                    tx.run(
                        f"MATCH (n:`{ENTITY_BASE_LABEL}` {{_project: $id}}) DETACH DELETE n",
                        {"id": project_id},
                    )
                    .consume()
                    .counters.nodes_deleted
                )
                proj = (
                    tx.run(
                        f"MATCH (p:`{PROJECT_LABEL}` {{id: $id}}) DETACH DELETE p",
                        {"id": project_id},
                    )
                    .consume()
                    .counters.nodes_deleted
                )
                return ents, proj

            entities_deleted, project_deleted = session.execute_write(_del)
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(delete_project): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e
    return {"entities_deleted": entities_deleted, "project_deleted": project_deleted}


def ingest(project_id: str, extraction: Extraction) -> dict[str, Any]:
    """추출 결과를 프로젝트 그래프에 병합(모든 데이터 연산을 단일 쓰기 트랜잭션으로 원자화)."""
    statements = build_ingest_statements(project_id, extraction)
    counters = {
        "nodes_created": 0,
        "relationships_created": 0,
        "labels_added": 0,
        "properties_set": 0,
    }
    if not statements:
        return {"stats": {"statements": 0, "counters": counters}}

    driver = get_driver()
    try:
        with driver.session(database=_DATABASE) as session:
            # 방어적: 제약이 없던 프로젝트(제약 도입 이전/수동 드롭)에서도 중복 _Entity를
            # 만들지 않도록 보장(스키마 op, 별도 auto-commit — 데이터 트랜잭션과 분리).
            _ensure_entity_constraint(session)

            def _write(tx):
                return [tx.run(st.cypher, st.params).consume().counters for st in statements]

            for c in session.execute_write(_write):
                counters["nodes_created"] += c.nodes_created
                counters["relationships_created"] += c.relationships_created
                counters["labels_added"] += c.labels_added
                counters["properties_set"] += c.properties_set
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(ingest): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e

    return {"stats": {"statements": len(statements), "counters": counters}}


def fetch_project_graph(project_id: str) -> dict[str, list[dict]]:
    """프로젝트 지식그래프를 시각화용 {nodes, links}로 조회(읽기 전용).

    노드 id=이름(프로젝트 내 고유). type=타입 라벨 중 첫 번째(색상용), types=전체 타입 라벨.
    """
    driver = get_driver()
    node_q = (
        f"MATCH (n:`{ENTITY_BASE_LABEL}` {{_project: $pid}}) "
        "RETURN n._name AS name, n.description AS description, "
        "[l IN labels(n) WHERE l <> $base] AS types "
        "ORDER BY name"
    )
    rel_q = (
        f"MATCH (a:`{ENTITY_BASE_LABEL}` {{_project: $pid}})"
        f"-[r]->(b:`{ENTITY_BASE_LABEL}` {{_project: $pid}}) "
        "RETURN a._name AS source, b._name AS target, type(r) AS type, "
        "r.description AS description "
        "ORDER BY type"
    )
    try:
        node_res = driver.execute_query(
            node_q,
            {"pid": project_id, "base": ENTITY_BASE_LABEL},
            routing_=neo4j.RoutingControl.READ,
            database_=_DATABASE,
        )
        rel_res = driver.execute_query(
            rel_q,
            {"pid": project_id},
            routing_=neo4j.RoutingControl.READ,
            database_=_DATABASE,
        )
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(project_graph): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e

    nodes = [
        {
            "id": r["name"],
            "name": r["name"],
            "type": (r["types"][0] if r["types"] else ""),
            "types": r["types"],
            "description": r["description"] or "",
        }
        for r in node_res.records
    ]
    links = [
        {
            "source": r["source"],
            "target": r["target"],
            "type": r["type"],
            "description": r["description"] or "",
        }
        for r in rel_res.records
    ]
    return {"nodes": nodes, "links": links}
