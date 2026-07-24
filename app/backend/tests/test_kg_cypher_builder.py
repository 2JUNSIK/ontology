"""v2 지식그래프 cypher_builder 단위테스트 (Neo4j 불필요).

게이트: 불변식 §2(순수 함수)·§3(인젝션 방지) — 이름/설명은 파라미터, 타입 라벨/관계타입은
화이트리스트+백틱.
"""

import pytest
from pydantic import ValidationError

from app.cypher_builder import (
    ENTITY_BASE_LABEL,
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
