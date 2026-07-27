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


def test_delete_entity_cascades_relations(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.delete_entity(project["id"], "녹조")
    assert res["nodes_deleted"] == 1
    assert res["relationships_deleted"] >= 2  # 녹조가 양끝이던 관계도 함께 삭제
    g = neo4j_service.fetch_project_graph(project["id"])
    assert "녹조" not in {n["name"] for n in g["nodes"]}
    assert g["links"] == []  # 남은 관계 없음


def test_delete_relation_keeps_endpoints(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.delete_relation(project["id"], "녹조", "남조류", "원인")
    assert res["relationships_deleted"] == 1
    g = neo4j_service.fetch_project_graph(project["id"])
    assert {"녹조", "남조류"} <= {n["name"] for n in g["nodes"]}  # 끝점 노드는 유지
    assert all(
        not (l["source"] == "녹조" and l["target"] == "남조류" and l["type"] == "원인")
        for l in g["links"]
    )


def test_delete_relation_wrong_type_is_noop(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.delete_relation(project["id"], "녹조", "남조류", "없는타입")
    assert res["relationships_deleted"] == 0  # 타입 불일치 → 아무것도 지우지 않음


def test_api_delete_entity_and_relation(project):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    pid = project["id"]
    client.post(f"/api/projects/{pid}/ingest", json=_ext().model_dump())

    r = client.request(
        "DELETE",
        f"/api/projects/{pid}/relations",
        json={"source": "녹조", "target": "남조류", "type": "원인"},
    )
    assert r.status_code == 200, r.text
    assert all(
        not (l["source"] == "녹조" and l["type"] == "원인") for l in r.json()["graph"]["links"]
    )

    r2 = client.request("DELETE", f"/api/projects/{pid}/entities", json={"name": "남조류"})
    assert r2.status_code == 200, r2.text
    assert "남조류" not in {n["name"] for n in r2.json()["graph"]["nodes"]}


def test_delete_entity_with_untrimmed_name_still_matches(project):
    # SHOULD-1 회귀 가드: API가 이름을 ingest와 동일하게 정제(trim/NFC)하므로 공백이 붙어도 삭제됨.
    from fastapi.testclient import TestClient

    from app.main import app

    neo4j_service_client = TestClient(app)
    pid = project["id"]
    neo4j_service_client.post(f"/api/projects/{pid}/ingest", json=_ext().model_dump())
    r = neo4j_service_client.request(
        "DELETE", f"/api/projects/{pid}/entities", json={"name": "  녹조  "}
    )
    assert r.status_code == 200, r.text
    assert "녹조" not in {n["name"] for n in r.json()["graph"]["nodes"]}


def test_delete_self_loop_relation(project):
    from app import neo4j_service
    from app.models import Extraction, Relation

    ext = Extraction(relations=[Relation(source="저수지", type="인접", target="저수지")])
    neo4j_service.ingest(project["id"], ext)
    res = neo4j_service.delete_relation(project["id"], "저수지", "저수지", "인접")
    assert res["relationships_deleted"] == 1
    g = neo4j_service.fetch_project_graph(project["id"])
    assert "저수지" in {n["name"] for n in g["nodes"]}  # 노드는 유지
    assert g["links"] == []


def test_delete_relation_reverse_direction_is_noop(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())  # (녹조)-[원인]->(남조류)
    res = neo4j_service.delete_relation(project["id"], "남조류", "녹조", "원인")  # 방향 반대
    assert res["relationships_deleted"] == 0
    g = neo4j_service.fetch_project_graph(project["id"])
    assert any(
        l["source"] == "녹조" and l["target"] == "남조류" and l["type"] == "원인"
        for l in g["links"]
    )  # 원래 관계 유지


def test_delete_entity_isolated_across_projects(project):
    from app import neo4j_service

    other = neo4j_service.create_project("IT_격리삭제", "")
    try:
        neo4j_service.ingest(project["id"], _ext())
        neo4j_service.ingest(other["id"], _ext())
        neo4j_service.delete_entity(project["id"], "녹조")
        # 다른 프로젝트의 동명 노드는 살아있어야 함
        g_other = neo4j_service.fetch_project_graph(other["id"])
        assert "녹조" in {n["name"] for n in g_other["nodes"]}
    finally:
        neo4j_service.delete_project(other["id"])


# ---- 읽기 경로(text-to-cypher): run_read_query 실행/격리/읽기전용 ----

_NODE_QUERY = (
    "MATCH (n:`_Entity` {_project: $pid})-[r]->(m:`_Entity` {_project: $pid}) "
    "RETURN n, r, m LIMIT 100"
)


def test_run_read_query_returns_graph(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.run_read_query(project["id"], _NODE_QUERY)
    names = {n["name"] for n in res["graph"]["nodes"]}
    assert {"녹조", "남조류"} <= names
    assert any(l["type"] == "원인" for l in res["graph"]["links"])
    # 노드 payload 포맷(프론트 재사용) 확인
    nokjo = next(n for n in res["graph"]["nodes"] if n["name"] == "녹조")
    assert "현상" in nokjo["types"]


def test_run_read_query_scalar_rows(project):
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.run_read_query(
        project["id"], "MATCH (n:`_Entity` {_project: $pid}) RETURN count(n) AS c"
    )
    assert res["columns"] == ["c"]
    assert res["rows"] and res["rows"][0][0] >= 3


def test_run_read_query_write_is_rejected_by_read_txn(project):
    # 정적 검증을 우회해 쓰기 Cypher를 직접 넘겨도 READ 트랜잭션이 드라이버 레벨에서 거부한다.
    from neo4j.exceptions import Neo4jError

    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    with pytest.raises(Neo4jError):
        neo4j_service.run_read_query(
            project["id"],
            "MATCH (n:`_Entity` {_project: $pid, _name: '녹조'}) DETACH DELETE n",
        )
    # 데이터가 실제로 지워지지 않았는지 확인
    g = neo4j_service.fetch_project_graph(project["id"])
    assert "녹조" in {n["name"] for n in g["nodes"]}


def test_run_read_query_post_filter_isolates_projects(project):
    # 쿼리가 프로젝트 필터를 생략(모든 _Entity)해도, 사후 매핑이 타 프로젝트 노드를 드롭한다.
    from app import neo4j_service

    other = neo4j_service.create_project("IT_읽기격리", "")
    try:
        neo4j_service.ingest(project["id"], _ext())
        neo4j_service.ingest(other["id"], Extraction(entities=[Entity(name="비밀노드", type="현상")]))
        # $pid는 검증 통과용으로 WHERE에 쓰되, MATCH는 전 프로젝트를 훑는 형태
        res = neo4j_service.run_read_query(
            project["id"],
            "MATCH (n:`_Entity`) WHERE n._project <> $pid OR n._project = $pid RETURN n LIMIT 500",
        )
        names = {n["name"] for n in res["graph"]["nodes"]}
        assert "녹조" in names
        assert "비밀노드" not in names  # 사후 필터가 타 프로젝트 드롭
    finally:
        neo4j_service.delete_project(other["id"])


def test_api_query_no_key_degrades(project):
    # conftest가 키 공백화 → generate_query None → 200 + error(무비용, 빈 그래프).
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post(f"/api/projects/{project['id']}/query", json={"question": "녹조와 연결된 노드 보여줘"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"]
    assert body["graph"]["nodes"] == []


def test_api_query_unknown_project_404():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post("/api/projects/nonexistent-id/query", json={"question": "질문"})
    assert r.status_code == 404


def test_run_read_query_rows_mask_other_project_nodes(project):
    # MUST-FIX-1: rows(표) 경로도 타 프로젝트 Node를 마스킹(None)해 이름 유출을 막는다.
    from app import neo4j_service

    other = neo4j_service.create_project("IT_rows격리", "")
    try:
        neo4j_service.ingest(project["id"], _ext())  # 녹조/남조류/…
        neo4j_service.ingest(
            other["id"], Extraction(entities=[Entity(name="비밀노드", type="현상")])
        )
        # 필터를 우회해 전 프로젝트 Node를 RETURN 시도(정적 검증 통과용으로 $pid/_project 포함)
        res = neo4j_service.run_read_query(
            project["id"],
            "MATCH (n:`_Entity`) WHERE n._project = $pid OR n._project <> $pid RETURN n LIMIT 500",
        )
        flat = [c for row in res["rows"] for c in row]
        assert "녹조" in flat  # 내 프로젝트 노드는 이름으로
        assert "비밀노드" not in flat  # 타 프로젝트 노드는 마스킹돼 이름이 새지 않음
        assert None in flat  # 타 프로젝트 Node → None
        assert "비밀노드" not in {n["name"] for n in res["graph"]["nodes"]}  # graph도 격리
    finally:
        neo4j_service.delete_project(other["id"])


def test_run_read_query_rows_scrub_internal_meta(project):
    # MUST-FIX-1: properties(n) 맵 반환에서 내부 메타(_project/_name)가 제거된다.
    from app import neo4j_service

    neo4j_service.ingest(project["id"], _ext())
    res = neo4j_service.run_read_query(
        project["id"],
        "MATCH (n:`_Entity` {_project: $pid, _name: '녹조'}) RETURN properties(n) AS p",
    )
    p = res["rows"][0][0]
    assert "_project" not in p and "_name" not in p
    assert p.get("description") == "남조류 과다 증식"


def test_api_query_rejects_write_cypher(project, monkeypatch):
    # 라우터: generate_query가 쓰기 Cypher를 내놔도 정적 검증에서 막혀 200 + error(무해).
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.routers import projects as prj
    from app.text_to_cypher import _QueryOut

    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)
    monkeypatch.setattr(
        prj,
        "generate_query",
        lambda *a, **k: _QueryOut(
            cypher="MATCH (n:`_Entity` {_project: $pid}) DETACH DELETE n",
            explanation="위험",
            result_kind="graph",
        ),
    )
    client = TestClient(app)
    r = client.post(f"/api/projects/{project['id']}/query", json={"question": "다 지워줘"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"]  # 정적 검증에서 거부
    assert body["graph"]["nodes"] == []


def test_api_query_graph_result(project, monkeypatch):
    # 라우터: 정상 읽기 Cypher → 그래프 결과 반환(end-to-end, Claude만 모킹).
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app
    from app.routers import projects as prj
    from app.text_to_cypher import _QueryOut

    neo4j_service_ingest(project["id"])
    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)
    monkeypatch.setattr(
        prj,
        "generate_query",
        lambda *a, **k: _QueryOut(
            cypher="MATCH (n:`_Entity` {_project: $pid}) RETURN n LIMIT 100",
            explanation="전체 노드",
            result_kind="graph",
        ),
    )
    client = TestClient(app)
    r = client.post(f"/api/projects/{project['id']}/query", json={"question": "전체 노드"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert not body["error"]
    assert body["cypher"].startswith("MATCH")
    assert "녹조" in {n["name"] for n in body["graph"]["nodes"]}


def neo4j_service_ingest(pid):
    from app import neo4j_service

    neo4j_service.ingest(pid, _ext())
