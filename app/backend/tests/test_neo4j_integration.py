r"""neo4j_service + /api/graph 통합 테스트 (M4). — **opt-in**.

기본 `pytest` 실행에서는 건너뛴다. 이유: commit은 `:_Schema` 메타를 전부 지우는
파괴적 동작이라, 개발용 Neo4j에 커밋해 둔 상태를 무심코 날릴 수 있다. 실제 실행은
환경변수로 명시적으로 켠 경우에만:

    $env:RUN_NEO4J_TESTS=1
    & "app\backend\.venv\Scripts\python.exe" -m pytest app\backend\tests\test_neo4j_integration.py

전용 테스트 라벨(IT_*)을 써서 만든 제약/메타를 테스트가 스스로 정리한다.
"""

import os

import pytest

from app.models import NodeLabel, OntologySchema, PropertyDef, RelationshipType

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_NEO4J_TESTS"),
    reason="RUN_NEO4J_TESTS 미설정 — Neo4j 통합 테스트 건너뜀(파괴적, opt-in)",
)

# 도메인 라벨과 충돌하지 않는 전용 테스트 라벨(정리 용이).
LABEL_A = "IT측정소"
LABEL_B = "IT측정값"
KEY_A = "IT코드"


def _it_schema() -> OntologySchema:
    return OntologySchema(
        nodes=[
            NodeLabel(
                label=LABEL_A,
                properties=[
                    PropertyDef(name=KEY_A, required=True),
                    PropertyDef(name="명칭"),
                ],
                key_property=KEY_A,
                description="통합테스트 측정소",
            ),
            NodeLabel(
                label=LABEL_B,
                properties=[PropertyDef(name="값", type="float")],
            ),
        ],
        relationships=[
            RelationshipType(type="IT관측지점", start_label=LABEL_B, end_label=LABEL_A),
        ],
    )


def _drop_test_constraints(driver):
    """LABEL_A 위에 만들어진 제약을 이름으로 조회해 제거."""
    res = driver.execute_query("SHOW CONSTRAINTS", database_="neo4j")
    for rec in res.records:
        labels = rec.get("labelsOrTypes") or []
        if LABEL_A in labels:
            name = rec["name"]
            driver.execute_query(f"DROP CONSTRAINT `{name}` IF EXISTS", database_="neo4j")


@pytest.fixture()
def driver():
    from neo4j.exceptions import ServiceUnavailable

    from app import neo4j_service

    d = neo4j_service.get_driver()
    try:
        d.verify_connectivity()
    except ServiceUnavailable:
        pytest.skip("Neo4j에 연결할 수 없음(컨테이너 미기동)")
    yield d
    # teardown: 메타 + 테스트 제약 정리
    d.execute_query("MATCH (s:`_Schema`) DETACH DELETE s", database_="neo4j")
    _drop_test_constraints(d)
    neo4j_service.close_driver()


def test_commit_then_fetch_graph_roundtrip(driver):
    from app import neo4j_service

    result = neo4j_service.commit_schema(_it_schema())
    assert result["stats"]["meta_nodes"] == 2
    assert result["stats"]["meta_relationships"] == 1
    assert result["stats"]["constraints"] == 1
    assert len(result["applied_cypher"]) == 4

    graph = neo4j_service.fetch_graph()
    ids = {n["id"] for n in graph["nodes"]}
    assert {LABEL_A, LABEL_B} == ids
    node_a = next(n for n in graph["nodes"] if n["id"] == LABEL_A)
    assert node_a["key_property"] == KEY_A
    assert {p["name"] for p in node_a["properties"]} == {KEY_A, "명칭"}

    assert len(graph["links"]) == 1
    link = graph["links"][0]
    assert link["source"] == LABEL_B
    assert link["target"] == LABEL_A
    assert link["type"] == "IT관측지점"


def test_constraint_actually_created(driver):
    from app import neo4j_service

    neo4j_service.commit_schema(_it_schema())
    res = driver.execute_query("SHOW CONSTRAINTS", database_="neo4j")
    on_label_a = [r for r in res.records if LABEL_A in (r.get("labelsOrTypes") or [])]
    assert on_label_a, "LABEL_A에 대한 UNIQUE 제약이 생성되어야 함"
    assert KEY_A in (on_label_a[0].get("properties") or [])


def test_recommit_is_idempotent_no_duplicate_meta(driver):
    from app import neo4j_service

    neo4j_service.commit_schema(_it_schema())
    neo4j_service.commit_schema(_it_schema())  # 재커밋
    graph = neo4j_service.fetch_graph()
    # 메타 초기화 덕분에 중복 없이 2노드/1관계 유지
    assert len(graph["nodes"]) == 2
    assert len(graph["links"]) == 1


def test_commit_via_api_and_graph_endpoint(driver):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    payload = _it_schema().model_dump()

    r = client.post("/api/schema/commit", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "applied_cypher" in body and "stats" in body

    g = client.get("/api/graph")
    assert g.status_code == 200
    ids = {n["id"] for n in g.json()["nodes"]}
    assert {LABEL_A, LABEL_B} == ids
