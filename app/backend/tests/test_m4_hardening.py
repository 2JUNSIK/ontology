"""M4 검수 반영 회귀 테스트 (Neo4j 불필요).

적대적 리뷰가 지적한 항목의 회귀 방지:
- 예약 식별자('_' 프리픽스) 거부 (MED#2)
- 인젝션 메타문자 라벨의 백틱 캡슐화 (§3)
- Neo4j 연결 불가 → 503 우아한 열화 (commit/graph, service + router)
"""

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable
from pydantic import ValidationError

from app import neo4j_service
from app.cypher_builder import build_constraints, escape_identifier
from app.main import app
from app.models import NodeLabel, OntologySchema, PropertyDef, RelationshipType

client = TestClient(app)


# ------------------- MED#2: 예약 '_' 프리픽스 거부 -------------------

@pytest.mark.parametrize("label", ["_Schema", "_SCHEMA_REL", "_internal", "_"])
def test_reserved_prefix_label_rejected(label):
    with pytest.raises(ValidationError):
        NodeLabel(label=label)


@pytest.mark.parametrize("rtype", ["_SCHEMA_REL", "_x"])
def test_reserved_prefix_reltype_rejected(rtype):
    with pytest.raises(ValidationError):
        RelationshipType(type=rtype, start_label="측정소", end_label="저수지")


def test_reserved_prefix_rel_endpoint_rejected():
    with pytest.raises(ValidationError):
        RelationshipType(type="측정", start_label="_Schema", end_label="저수지")


def test_property_name_may_start_with_underscore():
    # 속성명은 메타 라벨/관계타입이 아니므로 '_'를 허용한다(과도한 제약 방지).
    n = NodeLabel(label="측정소", properties=[PropertyDef(name="_hidden")])
    assert n.properties[0].name == "_hidden"


# ------------------- §3: 인젝션 메타문자 라벨의 백틱 캡슐화 -------------------

@pytest.mark.parametrize("evil", [")", "\\", ";", "'", "})", "n:Other", "*/"])
def test_escape_wraps_metachars_in_backticks(evil):
    # _clean_identifier를 통과하는 위험 메타문자들은 백틱 안에 리터럴로 갇혀야 한다.
    assert escape_identifier(evil) == f"`{evil}`"


def test_backtick_label_rejected_by_model():
    # 백틱 포함 라벨은 1차 방어선(_clean_identifier)에서 거부되어야 한다.
    with pytest.raises(ValidationError):
        NodeLabel(label="a`) DROP", properties=[PropertyDef(name="k")], key_property="k")


def test_constraint_ddl_confines_metachar_label_to_backticks():
    # _clean_identifier를 통과하는 메타문자 라벨은 DDL에서 백틱 안에만 등장(breakout 불가).
    schema = OntologySchema(
        nodes=[
            NodeLabel(label=") x", properties=[PropertyDef(name="k")], key_property="k")
        ]
    )
    (stmt,) = build_constraints(schema)
    assert "FOR (n:`) x`)" in stmt.cypher
    assert "REQUIRE n.`k` IS UNIQUE" in stmt.cypher


# ------------------- 503: service 계층 매핑 -------------------

class _RaisingDriver:
    """session()/execute_query()가 ServiceUnavailable을 던지는 가짜 드라이버."""

    def session(self, **kwargs):
        raise ServiceUnavailable("neo4j down")

    def execute_query(self, *args, **kwargs):
        raise ServiceUnavailable("neo4j down")


def test_commit_schema_maps_unavailable(monkeypatch):
    monkeypatch.setattr(neo4j_service, "get_driver", lambda: _RaisingDriver())
    with pytest.raises(neo4j_service.Neo4jUnavailable):
        neo4j_service.commit_schema(
            OntologySchema(nodes=[NodeLabel(label="측정소")])
        )


def test_fetch_graph_maps_unavailable(monkeypatch):
    monkeypatch.setattr(neo4j_service, "get_driver", lambda: _RaisingDriver())
    with pytest.raises(neo4j_service.Neo4jUnavailable):
        neo4j_service.fetch_graph()


# ------------------- 503: 라우터 계층 변환 -------------------

def test_commit_route_returns_503(monkeypatch):
    def _boom(_schema):
        raise neo4j_service.Neo4jUnavailable("down")

    # 라우터가 import한 이름을 패치
    monkeypatch.setattr("app.routers.schema.commit_schema", _boom)
    r = client.post("/api/schema/commit", json={"nodes": [{"label": "측정소"}], "relationships": []})
    assert r.status_code == 503
    assert "Neo4j" in r.json()["detail"]


def test_graph_route_returns_503(monkeypatch):
    def _boom():
        raise neo4j_service.Neo4jUnavailable("down")

    monkeypatch.setattr("app.routers.graph.fetch_graph", _boom)
    r = client.get("/api/graph")
    assert r.status_code == 503
    assert "Neo4j" in r.json()["detail"]
