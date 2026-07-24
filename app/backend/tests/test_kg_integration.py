r"""v2 프로젝트/지식그래프 통합 테스트 (실제 Neo4j) — **opt-in**.

    $env:RUN_NEO4J_TESTS=1
    & "app\backend\.venv\Scripts\python.exe" -m pytest app\backend\tests\test_kg_integration.py

전용 테스트 프로젝트를 만들어 쓰고, teardown에서 프로젝트+엔티티를 정리한다.
"""

import os

import pytest

from app.models import Entity, Extraction, Relation

pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_NEO4J_TESTS"),
    reason="RUN_NEO4J_TESTS 미설정 — Neo4j 통합 테스트 건너뜀(opt-in)",
)


def _ext() -> Extraction:
    return Extraction(
        entities=[
            Entity(name="녹조", type="현상", description="남조류 과다 증식"),
            Entity(name="남조류", type="생물"),
        ],
        relations=[
            Relation(source="녹조", type="원인", target="남조류"),
            # 끝점 '남조류세포수'는 엔티티에 없음 → stub 보강
            Relation(source="녹조", type="지표", target="남조류세포수"),
        ],
    )


@pytest.fixture()
def project():
    from neo4j.exceptions import ServiceUnavailable

    from app import neo4j_service

    d = neo4j_service.get_driver()
    try:
        d.verify_connectivity()
    except ServiceUnavailable:
        pytest.skip("Neo4j에 연결할 수 없음(컨테이너 미기동)")
    p = neo4j_service.create_project("IT_지식그래프테스트", "통합테스트")
    yield p
    neo4j_service.delete_project(p["id"])
    neo4j_service.close_driver()


def test_create_and_get_project(project):
    from app import neo4j_service

    got = neo4j_service.get_project(project["id"])
    assert got is not None
    assert got["name"] == "IT_지식그래프테스트"
    assert any(p["id"] == project["id"] for p in neo4j_service.list_projects())


def test_ingest_and_graph_roundtrip(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    g = neo4j_service.fetch_project_graph(project["id"])
    names = {n["name"] for n in g["nodes"]}
    assert names == {"녹조", "남조류", "남조류세포수"}  # stub 포함
    nokjo = next(n for n in g["nodes"] if n["name"] == "녹조")
    assert "현상" in nokjo["types"]
    assert nokjo["description"] == "남조류 과다 증식"
    assert len(g["links"]) == 2


def test_ingest_is_idempotent(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    neo4j_service.ingest(project["id"], _ext())  # 재입력 → 병합
    g = neo4j_service.fetch_project_graph(project["id"])
    assert len({n["name"] for n in g["nodes"]}) == 3  # 중복 없음
    assert len(g["links"]) == 2


def test_project_scoping_isolation(project):
    from app import neo4j_service

    other = neo4j_service.create_project("IT_다른프로젝트", "")
    try:
        neo4j_service.ingest(project["id"], _ext())
        g_other = neo4j_service.fetch_project_graph(other["id"])
        assert g_other["nodes"] == []  # 다른 프로젝트엔 안 섞임
    finally:
        neo4j_service.delete_project(other["id"])


def test_delete_project_removes_entities(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.delete_project(project["id"])
    assert res["entities_deleted"] >= 3
    assert res["project_deleted"] == 1
    assert neo4j_service.fetch_project_graph(project["id"])["nodes"] == []


def test_api_ingest_graph_and_404(project):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    pid = project["id"]

    r = client.post(f"/api/projects/{pid}/ingest", json=_ext().model_dump())
    assert r.status_code == 200, r.text
    assert {n["name"] for n in r.json()["graph"]["nodes"]} >= {"녹조", "남조류"}

    g = client.get(f"/api/projects/{pid}/graph")
    assert g.status_code == 200

    assert client.get("/api/projects/nonexistent-id/graph").status_code == 404


def test_api_extract_no_key_degrades(project):
    # conftest가 키를 공백화 → extract 엔드포인트가 빈 결과로 우아하게 열화(무비용).
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post(
        f"/api/projects/{project['id']}/extract",
        json={"text": "녹조는 남조류가 증식하는 현상이다"},
    )
    assert r.status_code == 200
    assert r.json()["entities"] == []
