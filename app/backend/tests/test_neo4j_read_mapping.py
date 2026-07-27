"""run_read_query 결과 매핑 순수 함수 단위테스트 (Neo4j 불필요).

_collect_graph의 프로젝트 격리 사후 필터·끊긴 관계 제외·중복 제거·상한을 검증한다.
neo4j 그래프 객체 하이드레이션(실 Node/Relationship 판별)은 test_kg_integration(opt-in)에서 다룬다.
"""

from app.neo4j_service import _collect_graph, _node_payload, _scalarize

BASE = "_Entity"


def _n(name, project="p", types=(), desc=""):
    """테스트용 (labels, props) 튜플."""
    labels = [BASE, *types]
    props = {"_name": name, "_project": project, "description": desc}
    return labels, props


def test_node_payload_basic():
    labels, props = _n("녹조", types=("현상",), desc="설명")
    p = _node_payload(labels, props)
    assert p == {
        "id": "녹조", "name": "녹조", "type": "현상", "types": ["현상"], "description": "설명",
    }


def test_node_payload_untyped():
    labels, props = _n("x")
    p = _node_payload(labels, props)
    assert p["type"] == "" and p["types"] == []


def test_collect_graph_nodes_and_links():
    a = _n("녹조", types=("현상",))
    b = _n("남조류", types=("생물",))
    rels = [("원인", a, b, {"description": "설명"})]
    g = _collect_graph([a, b], rels, "p", 300, 500)
    assert {n["name"] for n in g["nodes"]} == {"녹조", "남조류"}
    assert g["links"] == [
        {"source": "녹조", "target": "남조류", "type": "원인", "description": "설명"}
    ]


def test_collect_graph_drops_other_project_nodes():
    mine = _n("녹조", project="p", types=("현상",))
    other = _n("비밀", project="other", types=("현상",))
    g = _collect_graph([mine, other], [], "p", 300, 500)
    assert {n["name"] for n in g["nodes"]} == {"녹조"}  # 다른 프로젝트 사후 드롭


def test_collect_graph_drops_relation_with_other_project_endpoint():
    mine = _n("녹조", project="p")
    other = _n("비밀", project="other")
    rels = [("원인", mine, other, {})]
    g = _collect_graph([mine, other], rels, "p", 300, 500)
    assert g["links"] == []  # 끝점이 다른 프로젝트 → 관계 드롭
    assert {n["name"] for n in g["nodes"]} == {"녹조"}


def test_collect_graph_relation_endpoint_augments_nodes():
    # 관계로만 등장한 끝점도 노드 집합에 포함하고 라벨을 보강한다.
    a = _n("녹조", types=("현상",))
    b = _n("남조류", types=("생물",))
    g = _collect_graph([], [("원인", a, b, {})], "p", 300, 500)
    assert {n["name"] for n in g["nodes"]} == {"녹조", "남조류"}
    nokjo = next(n for n in g["nodes"] if n["name"] == "녹조")
    assert nokjo["types"] == ["현상"]


def test_collect_graph_dedups_relations():
    a = _n("A")
    b = _n("B")
    rels = [("rel", a, b, {"description": "1"}), ("rel", a, b, {"description": "2"})]
    g = _collect_graph([a, b], rels, "p", 300, 500)
    assert len(g["links"]) == 1
    assert g["links"][0]["description"] == "1"  # 첫 등장 유지(결정적)


def test_collect_graph_skips_nameless_or_empty():
    empty = ([BASE], {"_project": "p"})  # _name 없음
    g = _collect_graph([empty], [], "p", 300, 500)
    assert g["nodes"] == []


def test_collect_graph_node_limit():
    nodes = [_n(f"n{i}") for i in range(10)]
    g = _collect_graph(nodes, [], "p", 3, 500)
    assert len(g["nodes"]) == 3
    assert [n["name"] for n in g["nodes"]] == ["n0", "n1", "n2"]  # 순서 보존


def test_collect_graph_link_pruned_when_endpoint_over_limit():
    # 노드 상한으로 끝점이 잘려나가면 그 관계도 제거(끊긴 엣지 방지).
    nodes = [_n(f"n{i}") for i in range(5)]
    rels = [("rel", nodes[0], nodes[4], {})]
    g = _collect_graph(nodes, rels, "p", 3, 500)
    assert len(g["nodes"]) == 3
    assert g["links"] == []  # n4가 상한으로 잘려 관계 제거


# ---- 강화(MUST-FIX-1): _scalarize 격리 사후 필터 + 메타 스크럽 ----
# (Node/Relationship 판별은 neo4j 하이드레이션 객체가 필요 → test_kg_integration에서 라이브 검증.
#  여기서는 dict/스칼라/중첩 경로를 순수 검증한다.)

def test_scalarize_passthrough_scalars():
    assert _scalarize("녹조", "p") == "녹조"
    assert _scalarize(42, "p") == 42
    assert _scalarize(True, "p") is True
    assert _scalarize(None, "p") is None


def test_scalarize_scrubs_internal_meta_keys_in_dict():
    # 맵 프로젝션(properties(n) 등)에서 '_' 프리픽스 내부 메타는 제거된다.
    out = _scalarize({"_project": "p", "_name": "녹조", "description": "설명"}, "p")
    assert out == {"description": "설명"}
    assert "_project" not in out and "_name" not in out


def test_scalarize_recurses_lists_and_nested_dicts():
    out = _scalarize([{"_name": "x", "y": 1}, "z"], "p")
    assert out == [{"y": 1}, "z"]


def test_scalarize_stringifies_unknown_types():
    class _Weird:
        def __str__(self):
            return "WEIRD"

    assert _scalarize(_Weird(), "p") == "WEIRD"
