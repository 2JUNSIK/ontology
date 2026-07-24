"""cypher_builder 순수 단위테스트 (M4).

핵심 게이트: 설계 불변식 §2(순수 함수)·§3(인젝션 방지)를 검증한다. Neo4j 불필요.
"""

import json

import pytest

from app.cypher_builder import (
    META_NODE_LABEL,
    META_REL_TYPE,
    build_commit_statements,
    build_constraints,
    build_meta_nodes,
    build_meta_rels,
    escape_identifier,
)
from app.models import NodeLabel, OntologySchema, PropertyDef, RelationshipType


def _schema() -> OntologySchema:
    return OntologySchema(
        nodes=[
            NodeLabel(
                label="측정소",
                properties=[
                    PropertyDef(name="측정소코드", type="string", required=True),
                    PropertyDef(name="명칭"),
                ],
                key_property="측정소코드",
                description="수질 측정 지점",
            ),
            NodeLabel(
                label="측정값",
                properties=[PropertyDef(name="값", type="float")],
                key_property=None,  # 키 없음 → 제약 생성 안 함
            ),
        ],
        relationships=[
            RelationshipType(type="관측지점", start_label="측정값", end_label="측정소"),
        ],
    )


# ------------------------- escape_identifier -------------------------

def test_escape_identifier_wraps_korean():
    assert escape_identifier("측정소") == "`측정소`"


def test_escape_identifier_rejects_backtick():
    # 모델 방어선(_clean_identifier)이 백틱을 거부 → cypher_builder도 국소적으로 차단
    with pytest.raises(ValueError):
        escape_identifier("측정" + chr(0x60) + "소")  # 0x60 = 백틱


def test_escape_identifier_rejects_control_char():
    # 탭(U+0009, 카테고리 Cc)은 금지 문자 → 거부되어야 한다.
    with pytest.raises(ValueError):
        escape_identifier("측정\t소")


def test_escape_identifier_rejects_null_byte():
    with pytest.raises(ValueError):
        escape_identifier("측정\x00소")


def test_escape_identifier_rejects_empty():
    with pytest.raises(ValueError):
        escape_identifier("   ")


# ------------------------- build_constraints -------------------------

def test_constraints_only_for_key_property():
    stmts = build_constraints(_schema())
    # 측정소만 key_property가 있으므로 제약은 1개
    assert len(stmts) == 1
    st = stmts[0]
    assert st.kind == "constraint"
    assert st.params == {}
    assert "CREATE CONSTRAINT IF NOT EXISTS" in st.cypher
    assert "FOR (n:`측정소`)" in st.cypher
    assert "REQUIRE n.`측정소코드` IS UNIQUE" in st.cypher


def test_constraints_empty_when_no_keys():
    schema = OntologySchema(
        nodes=[NodeLabel(label="측정값", properties=[PropertyDef(name="값")])]
    )
    assert build_constraints(schema) == []


# ------------------------- build_meta_nodes (인젝션 방지) -------------------------

def test_meta_nodes_bind_values_as_params_not_ddl():
    st = build_meta_nodes(_schema())
    assert st.kind == "meta_node"
    # 라벨/속성값은 파라미터로만 전달되고 Cypher 문자열엔 도메인 문자열이 없어야 한다
    assert "$rows" in st.cypher
    assert "UNWIND $rows AS row" in st.cypher
    assert "측정소" not in st.cypher          # 도메인 라벨이 DDL에 새지 않음
    assert "측정소코드" not in st.cypher
    # 메타 라벨(_Schema)만 식별자로 escape되어 등장
    assert f"`{META_NODE_LABEL}`" in st.cypher
    # 파라미터 rows 검증
    rows = st.params["rows"]
    labels = {r["label"] for r in rows}
    assert labels == {"측정소", "측정값"}
    stn = next(r for r in rows if r["label"] == "측정소")
    assert stn["key_property"] == "측정소코드"
    props = json.loads(stn["properties_json"])
    assert {p["name"] for p in props} == {"측정소코드", "명칭"}


def test_meta_nodes_properties_json_is_valid_json():
    st = build_meta_nodes(_schema())
    for r in st.params["rows"]:
        parsed = json.loads(r["properties_json"])  # 예외 없어야 함
        assert isinstance(parsed, list)


# ------------------------- build_meta_rels -------------------------

def test_meta_rels_store_type_as_property():
    st = build_meta_rels(_schema())
    assert st.kind == "meta_rel"
    assert "$rows" in st.cypher
    # 도메인 관계타입은 rel_type 속성(파라미터)으로만 — 동적 관계타입 DDL 금지
    assert "관측지점" not in st.cypher
    assert "rel_type: row.type" in st.cypher
    assert f"`{META_REL_TYPE}`" in st.cypher
    row = st.params["rows"][0]
    assert row["type"] == "관측지점"
    assert row["start_label"] == "측정값"
    assert row["end_label"] == "측정소"


# ------------------------- build_commit_statements (순서/종류) -------------------------

def test_commit_statement_order_and_kinds():
    stmts = build_commit_statements(_schema())
    kinds = [s.kind for s in stmts]
    # 제약 → 메타 초기화 → 메타노드 → 메타관계 순
    assert kinds == ["constraint", "meta_clear", "meta_node", "meta_rel"]


def test_commit_empty_schema_clears_only():
    stmts = build_commit_statements(OntologySchema())
    kinds = [s.kind for s in stmts]
    assert kinds == ["meta_clear"]  # 노드/관계 없음 → 초기화만


def test_commit_is_pure_no_mutation():
    schema = _schema()
    snapshot = schema.model_dump_json()
    build_commit_statements(schema)
    build_constraints(schema)
    build_meta_nodes(schema)
    # 입력 스키마가 변형되지 않아야 함(순수 함수, §2)
    assert schema.model_dump_json() == snapshot
