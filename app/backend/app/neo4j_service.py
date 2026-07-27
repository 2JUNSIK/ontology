"""Neo4j 실행 계층 (v2).

관심사 분리(불변식 §2): Cypher '생성'은 cypher_builder(순수 함수), '실행'은 여기가 담당.
neo4j 파이썬 드라이버 **6.x** API 기준.

- 드라이버는 **지연 초기화 싱글턴**. 앱 종료 시 close_driver()로 정리(main.py lifespan).
- Neo4j 미가동/연결 불가는 ServiceUnavailable을 잡아 `Neo4jUnavailable`로 승격 →
  라우터가 503으로 변환한다(백엔드가 죽지 않고 우아하게 열화).
- **스키마 DDL(CREATE CONSTRAINT)** 은 auto-commit 트랜잭션(`session.run`)으로 실행한다.
  각 문이 개별 트랜잭션이라 한 트랜잭션 내 스키마/데이터 혼용 금지 규칙을 자연히 회피한다.
"""

from __future__ import annotations

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
    build_entity_constraint,
    build_ingest_statements,
)
from .models import Extraction

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


def delete_entity(project_id: str, name: str) -> dict[str, int]:
    """프로젝트 내 이름=name 엔티티를 삭제한다(연결된 관계도 DETACH DELETE로 함께 제거).

    값(project_id·name)은 전부 파라미터 바인딩 → 인젝션 표면 없음. 관리형 쓰기 트랜잭션.
    """
    driver = get_driver()
    try:
        with driver.session(database=_DATABASE) as session:

            def _del(tx):
                return (
                    tx.run(
                        f"MATCH (n:`{ENTITY_BASE_LABEL}` {{_project: $pid, _name: $name}}) "
                        "DETACH DELETE n",
                        {"pid": project_id, "name": name},
                    )
                    .consume()
                    .counters
                )

            c = session.execute_write(_del)
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(delete_entity): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e
    return {"nodes_deleted": c.nodes_deleted, "relationships_deleted": c.relationships_deleted}


def delete_relation(project_id: str, source: str, target: str, rel_type: str) -> dict[str, int]:
    """프로젝트 내 (source)-[rel_type]->(target) 관계 1개를 삭제한다.

    관계타입은 `type(r) = $rtype` 로 비교해 **동적 식별자를 Cypher에 넣지 않는다**(값·이름과
    함께 전부 파라미터 바인딩 → 인젝션 표면 제거). 끝점 노드는 남기고 관계만 삭제한다.
    """
    driver = get_driver()
    try:
        with driver.session(database=_DATABASE) as session:

            def _del(tx):
                return (
                    tx.run(
                        f"MATCH (a:`{ENTITY_BASE_LABEL}` {{_project: $pid, _name: $source}})"
                        f"-[r]->(b:`{ENTITY_BASE_LABEL}` {{_project: $pid, _name: $target}}) "
                        "WHERE type(r) = $rtype "
                        "DELETE r",
                        {"pid": project_id, "source": source, "target": target, "rtype": rel_type},
                    )
                    .consume()
                    .counters
                )

            c = session.execute_write(_del)
    except ServiceUnavailable as e:
        logger.warning("Neo4j 연결 불가(delete_relation): %s", type(e).__name__)
        raise Neo4jUnavailable(str(e)) from e
    return {"relationships_deleted": c.relationships_deleted}
