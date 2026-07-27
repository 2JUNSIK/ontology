"""v2 지식그래프 cypher_builder 단위테스트 (Neo4j 불필요).

게이트: 불변식 §2(순수 함수)·§3(인젝션 방지) — 이름/설명은 파라미터, 타입 라벨/관계타입은
화이트리스트+백틱.
"""

import pytest
from pydantic import ValidationError

from app.cypher_builder import (
    ENTITY_BASE_LABEL,
    assert_read_only_cypher,
    build_entity_constraint,
    build_ingest_statements,
)
from app.models import Entity, Extraction, Relation


def _extraction() -> Extraction:
    return Extraction(
        entities=[
            Entity(name="녹조", type="현상", description="남조류 과다 증식"),
            Entity(name="남조류", type="생물"),
            Entity(name="조류경보제", type="제도"),
            Entity(name="관심", type="경보단계"),
        ],
        relations=[
            Relation(source="녹조", type="원인", target="남조류"),
            Relation(source="조류경보제", type="단계", target="관심"),
            # 끝점 '남조류세포수'는 엔티티 목록에 없음 → stub로 보강되어야 함
            Relation(source="관심", type="기준지표", target="남조류세포수",
                     description="세포수 1000 이상"),
        ],
    )


def _by_kind(stmts, kind):
    return [s for s in stmts if s.kind == kind]


# ------------------------- 제약 -------------------------

def test_entity_constraint_composite_unique():
    st = build_entity_constraint()
    assert st.kind == "constraint"
    assert "CREATE CONSTRAINT IF NOT EXISTS" in st.cypher
    assert f"FOR (n:`{ENTITY_BASE_LABEL}`)" in st.cypher
    assert "REQUIRE (n._project, n._name) IS UNIQUE" in st.cypher


# ------------------------- ingest: 엔티티 -------------------------

def test_ingest_entities_bound_as_params():
    stmts = build_ingest_statements("proj-1", _extraction())
    (em,) = _by_kind(stmts, "entity_merge")
    # 이름/설명/project_id는 전부 파라미터. Cypher 문자열엔 도메인 이름이 없어야 한다.
    assert "$rows" in em.cypher and "$pid" in em.cypher
    assert "녹조" not in em.cypher
    assert "proj-1" not in em.cypher
    assert em.params["pid"] == "proj-1"
    names = {r["name"] for r in em.params["rows"]}
    # 관계 끝점 stub(남조류세포수) 포함 5개
    assert names == {"녹조", "남조류", "조류경보제", "관심", "남조류세포수"}
    desc = {r["name"]: r["description"] for r in em.params["rows"]}
    assert desc["녹조"] == "남조류 과다 증식"
    assert desc["남조류세포수"] == ""  # stub 무설명


def test_ingest_type_labels_grouped_and_escaped():
    stmts = build_ingest_statements("proj-1", _extraction())
    types = _by_kind(stmts, "entity_type")
    # 타입 4종(현상/생물/제도/경보단계)
    assert len(types) == 4
    for st in types:
        assert "UNWIND $names AS nm" in st.cypher
        assert "SET n:`" in st.cypher  # 타입 라벨은 백틱 식별자
        assert isinstance(st.params["names"], list)
    # '현상' 타입 문에는 '녹조'만 이름 파라미터로
    hyeonsang = next(s for s in types if "`현상`" in s.cypher)
    assert hyeonsang.params["names"] == ["녹조"]


def test_ingest_relations_grouped_and_bound():
    stmts = build_ingest_statements("proj-1", _extraction())
    rels = _by_kind(stmts, "relation")
    assert len(rels) == 3  # 원인/단계/기준지표
    r_typenames = set()
    for st in rels:
        assert "MERGE (a)-[rel:`" in st.cypher   # 관계타입은 백틱 식별자
        assert "$rows" in st.cypher and "$pid" in st.cypher
        # 끝점 이름은 파라미터로만
        for row in st.params["rows"]:
            assert row["source"] and row["target"]
        r_typenames |= {row["source"] for row in st.params["rows"]}
    # 관계 끝점 이름이 Cypher 식별자 위치에 새지 않았는지(대표 확인)
    gijun = next(s for s in rels if "`기준지표`" in s.cypher)
    assert "남조류세포수" not in gijun.cypher
    assert gijun.params["rows"][0]["target"] == "남조류세포수"


def test_ingest_statement_kinds_order():
    stmts = build_ingest_statements("p", _extraction())
    kinds = [s.kind for s in stmts]
    # 엔티티 → 타입 → 관계 순
    assert kinds[0] == "entity_merge"
    assert kinds.count("entity_type") == 4
    assert kinds[-1] == "relation" or "relation" in kinds
    # entity_merge가 모든 entity_type/relation보다 먼저
    assert kinds.index("entity_merge") < kinds.index("entity_type")
    assert kinds.index("entity_type") < kinds.index("relation")


# ------------------------- 인젝션 방지 -------------------------

def test_ingest_metachar_type_confined_to_backticks():
    ext = Extraction(
        entities=[Entity(name="x", type=") DETACH DELETE n //")],
    )
    stmts = build_ingest_statements("p", ext)
    (t,) = _by_kind(stmts, "entity_type")
    assert "SET n:`) DETACH DELETE n //`" in t.cypher  # 백틱 안에 리터럴로 갇힘


def test_ingest_selfloop_relation_ok():
    ext = Extraction(relations=[Relation(source="A", type="관련", target="A")])
    stmts = build_ingest_statements("p", ext)
    (em,) = _by_kind(stmts, "entity_merge")
    assert {r["name"] for r in em.params["rows"]} == {"A"}  # 자기루프 끝점 1개
    (rel,) = _by_kind(stmts, "relation")
    assert rel.params["rows"][0]["source"] == rel.params["rows"][0]["target"] == "A"


def test_ingest_is_pure():
    ext = _extraction()
    snap = ext.model_dump_json()
    build_ingest_statements("p", ext)
    assert ext.model_dump_json() == snap


# ------------------------- 모델 검증 (KG) -------------------------

def test_entity_type_underscore_prefix_rejected():
    with pytest.raises(ValidationError):
        Entity(name="x", type="_Entity")


def test_entity_empty_type_allowed():
    assert Entity(name="x", type="   ").type == ""
    assert Entity(name="x").type == ""


def test_entity_name_rejects_control_char():
    with pytest.raises(ValidationError):
        Entity(name="a\tb")


def test_entity_name_allows_backtick_as_value():
    # 이름은 값(파라미터) — 백틱 허용(식별자와 달리).
    assert Entity(name="a`b").name == "a`b"


def test_relation_type_required_nonempty():
    with pytest.raises(ValidationError):
        Relation(source="A", type="   ", target="B")


def test_entity_name_length_boundary():
    Entity(name="a" * 500)  # 경계값 OK
    with pytest.raises(ValidationError):
        Entity(name="a" * 501)


# ------------------------- 관계 중복 제거(LOW-1 회귀) -------------------------

def test_ingest_dedups_duplicate_relations():
    ext = Extraction(
        relations=[
            Relation(source="A", type="rel", target="B", description="첫"),
            Relation(source="A", type="rel", target="B", description="둘"),
        ]
    )
    stmts = build_ingest_statements("p", ext)
    rels = _by_kind(stmts, "relation")
    assert len(rels) == 1
    assert len(rels[0].params["rows"]) == 1  # 동일 (source,type,target) 1개로 병합
    assert rels[0].params["rows"][0]["description"] == "첫"  # 첫 등장 설명 유지(결정적)


def test_ingest_dedup_upgrades_empty_description():
    ext = Extraction(
        relations=[
            Relation(source="A", type="rel", target="B", description=""),
            Relation(source="A", type="rel", target="B", description="채움"),
        ]
    )
    stmts = build_ingest_statements("p", ext)
    rows = _by_kind(stmts, "relation")[0].params["rows"]
    assert rows[0]["description"] == "채움"  # 빈 설명은 비어있지 않은 것으로 승격


# ============================================================
# 읽기 경로(text-to-cypher): assert_read_only_cypher 정적 검증
# ============================================================

# 정상 통과: MATCH/WHERE/RETURN + $pid 프로젝트 필터
_OK_QUERY = (
    "MATCH (n:`_Entity` {_project: $pid})-[r]-(m:`_Entity` {_project: $pid}) "
    "RETURN n, r, m LIMIT 100"
)


def test_read_only_accepts_valid_match():
    assert assert_read_only_cypher(_OK_QUERY) is None


def test_read_only_accepts_aggregation_with_pid():
    q = "MATCH (n:`_Entity` {_project: $pid}) RETURN count(n) AS c"
    assert assert_read_only_cypher(q) is None


def test_read_only_allows_trailing_semicolon():
    assert assert_read_only_cypher(_OK_QUERY + " ;") is None


@pytest.mark.parametrize(
    "bad",
    [
        "MATCH (n {_project:$pid}) DETACH DELETE n",
        "MATCH (n {_project:$pid}) DELETE n",
        "MATCH (n {_project:$pid}) SET n.x = 1 RETURN n",
        "MATCH (n {_project:$pid}) REMOVE n:Label RETURN n",
        "CREATE (n {_project:$pid}) RETURN n",
        "MERGE (n {_project:$pid}) RETURN n",
        "MATCH (n {_project:$pid}) WITH n CALL db.labels() YIELD label RETURN label",
        "CALL apoc.periodic.iterate('MATCH (n) RETURN n','DELETE n',{}) YIELD batches RETURN batches",
        "LOAD CSV FROM 'file:///x.csv' AS row RETURN row",
        "MATCH (n {_project:$pid}) FOREACH (x IN [1] | SET n.y = x) RETURN n",
        "DROP CONSTRAINT c",
        "USE somedb MATCH (n {_project:$pid}) RETURN n",
    ],
)
def test_read_only_rejects_write_keywords(bad):
    with pytest.raises(ValueError):
        assert_read_only_cypher(bad)


def test_read_only_rejects_lowercase_write_keyword():
    # 대소문자 무시 — 소문자 delete도 거부
    with pytest.raises(ValueError):
        assert_read_only_cypher("match (n {_project:$pid}) delete n")


def test_read_only_rejects_multiple_statements():
    with pytest.raises(ValueError):
        assert_read_only_cypher(
            "MATCH (n {_project:$pid}) RETURN n; MATCH (m {_project:$pid}) RETURN m"
        )


def test_read_only_rejects_missing_pid():
    # $pid 없음 → 프로젝트 격리 붕괴 위험 → 거부
    with pytest.raises(ValueError):
        assert_read_only_cypher("MATCH (n:`_Entity`) RETURN n LIMIT 10")


def test_read_only_rejects_empty():
    for bad in ["", "   ", None]:
        with pytest.raises(ValueError):
            assert_read_only_cypher(bad)  # type: ignore[arg-type]


def test_read_only_ignores_keyword_inside_string_literal():
    # 리터럴 안의 'DELETE'는 절이 아니라 검색어 → 통과해야 한다(오탐 없음).
    q = "MATCH (n:`_Entity` {_project: $pid}) WHERE n._name = 'DELETE ME' RETURN n"
    assert assert_read_only_cypher(q) is None


def test_read_only_ignores_semicolon_inside_string_literal():
    q = "MATCH (n:`_Entity` {_project: $pid}) WHERE n._name = 'a;b' RETURN n"
    assert assert_read_only_cypher(q) is None


def test_read_only_ignores_keyword_inside_backtick_identifier():
    # 백틱 식별자 안의 'DELETE'는 라벨 이름 → 절이 아니므로 통과(오탐 없음).
    q = "MATCH (n:`DELETE` {_project: $pid}) RETURN n"
    assert assert_read_only_cypher(q) is None


def test_read_only_pid_only_inside_literal_is_rejected():
    # $pid가 리터럴 안에만 있으면 실제 파라미터가 아니므로 거부돼야 한다(마스킹 후 미검출).
    q = "MATCH (n:`_Entity`) WHERE n._name = '$pid' RETURN n"
    with pytest.raises(ValueError):
        assert_read_only_cypher(q)


def test_read_only_does_not_false_positive_on_settings_identifier():
    # 'SET'이 식별자(settings)의 일부일 때 오탐하지 않는다(\b 단어 경계).
    q = "MATCH (n:`_Entity` {_project: $pid}) RETURN n.settings AS s"
    assert assert_read_only_cypher(q) is None


# ---- 강화(MUST-FIX): 격리 검증 + 주석 마스킹 ----

def test_read_only_rejects_missing_project_prop():
    # $pid는 있어도 _project 필터가 없으면 거부(격리 필터 누락).
    with pytest.raises(ValueError):
        assert_read_only_cypher("MATCH (n:`_Entity`) WHERE n._name = $pid RETURN n")


def test_read_only_rejects_pid_only_in_comment():
    # $pid/_project가 주석 안에만 있으면 실제 필터가 아니므로 거부(주석 우회 차단).
    with pytest.raises(ValueError):
        assert_read_only_cypher("MATCH (m:`_Entity`) RETURN m LIMIT 100 // needs $pid _project")
    with pytest.raises(ValueError):
        assert_read_only_cypher("MATCH (m:`_Entity`) RETURN m /* $pid _project */ LIMIT 100")


def test_read_only_rejects_pid_substring_lookalike():
    # $pidding 등 substring 유사어는 $pid 파라미터로 인정하지 않는다(단어 경계).
    with pytest.raises(ValueError):
        assert_read_only_cypher("MATCH (n:`_Entity` {_project: $pidding}) RETURN n")


def test_read_only_ignores_keyword_in_line_comment():
    # 한 줄 주석 안의 쓰기 키워드는 무시(오탐 없음). 정상 통과.
    q = "MATCH (n:`_Entity` {_project: $pid}) RETURN n // 이 쿼리는 DELETE 안 함"
    assert assert_read_only_cypher(q) is None


def test_read_only_ignores_keyword_in_block_comment():
    q = "/* SET REMOVE 주의 */ MATCH (n:`_Entity` {_project: $pid}) RETURN n"
    assert assert_read_only_cypher(q) is None


def test_read_only_allows_trailing_line_comment_after_semicolon():
    # 세미콜론 뒤 주석만 남으면(다중문 아님) 통과.
    q = "MATCH (n:`_Entity` {_project: $pid}) RETURN n ; // 끝"
    assert assert_read_only_cypher(q) is None
