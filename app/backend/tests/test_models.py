"""models.py 엣지케이스 테스트 (설계 불변식 §1 검증)."""

import pytest
from pydantic import ValidationError

from app.models import (
    EnrichmentResponse,
    NodeLabel,
    OntologySchema,
    PropertyDef,
    RelationshipType,
    Suggestion,
)

# ---------------------------------------------------------------- 정상 케이스


def test_property_default_type_is_string():
    p = PropertyDef(name="명칭")
    assert p.type == "string"
    assert p.required is False


def test_node_label_trims_whitespace():
    n = NodeLabel(label="  측정소  ")
    assert n.label == "측정소"


def test_valid_schema_roundtrip():
    schema = OntologySchema(
        nodes=[
            NodeLabel(label="측정소", properties=[PropertyDef(name="측정소코드")], key_property="측정소코드"),
            NodeLabel(label="수질항목", properties=[PropertyDef(name="항목명")], key_property="항목명"),
        ],
        relationships=[RelationshipType(type="측정", start_label="측정소", end_label="수질항목")],
    )
    dumped = schema.model_dump()
    assert OntologySchema.model_validate(dumped) == schema


# ---------------------------------------------------------------- 식별자 검증


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_empty_label_rejected(bad):
    with pytest.raises(ValidationError):
        NodeLabel(label=bad)


def test_backtick_in_label_rejected():
    # DDL 인젝션 1차 방어선: 백틱 금지
    with pytest.raises(ValidationError):
        NodeLabel(label="측정소`) DROP DATABASE neo4j //")


def test_control_char_in_label_rejected():
    with pytest.raises(ValidationError):
        NodeLabel(label="측정\x00소")


def test_too_long_label_rejected():
    with pytest.raises(ValidationError):
        NodeLabel(label="측" * 101)


def test_backtick_in_relationship_type_rejected():
    with pytest.raises(ValidationError):
        RelationshipType(type="측정`", start_label="측정소", end_label="수질항목")


# ---------------------------------------------------------------- 구조 정합성


def test_key_property_must_exist_in_properties():
    with pytest.raises(ValidationError):
        NodeLabel(label="측정소", properties=[PropertyDef(name="명칭")], key_property="측정소코드")


def test_key_property_none_is_allowed():
    n = NodeLabel(label="측정값", properties=[PropertyDef(name="값", type="float")], key_property=None)
    assert n.key_property is None


def test_duplicate_property_names_rejected():
    with pytest.raises(ValidationError):
        NodeLabel(label="측정소", properties=[PropertyDef(name="명칭"), PropertyDef(name="명칭")])


def test_duplicate_node_labels_rejected():
    with pytest.raises(ValidationError):
        OntologySchema(nodes=[NodeLabel(label="저수지"), NodeLabel(label="저수지")])


def test_duplicate_relationship_signature_rejected():
    rel = RelationshipType(type="측정", start_label="측정소", end_label="수질항목")
    rel2 = RelationshipType(type="측정", start_label="측정소", end_label="수질항목")
    with pytest.raises(ValidationError):
        OntologySchema(
            nodes=[NodeLabel(label="측정소"), NodeLabel(label="수질항목")],
            relationships=[rel, rel2],
        )


def test_same_type_different_endpoints_is_allowed():
    # 관계 타입이 같아도 (start,end)가 다르면 별개 관계
    schema = OntologySchema(
        nodes=[NodeLabel(label="A"), NodeLabel(label="B"), NodeLabel(label="C")],
        relationships=[
            RelationshipType(type="rel", start_label="A", end_label="B"),
            RelationshipType(type="rel", start_label="A", end_label="C"),
        ],
    )
    assert len(schema.relationships) == 2


# ---------------------------------------------------------------- 경고(비예외)


def test_consistency_warnings_flags_unknown_labels():
    schema = OntologySchema(
        nodes=[NodeLabel(label="측정소", properties=[PropertyDef(name="c")], key_property="c")],
        relationships=[RelationshipType(type="측정", start_label="측정소", end_label="수질항목")],
    )
    warnings = schema.consistency_warnings()
    assert any("수질항목" in w for w in warnings)


def test_consistency_warnings_flags_missing_key():
    schema = OntologySchema(nodes=[NodeLabel(label="측정값")])
    assert any("key_property" in w for w in schema.consistency_warnings())


def test_node_lookup_helper():
    schema = OntologySchema(nodes=[NodeLabel(label="저수지")])
    assert schema.node("저수지") is not None
    assert schema.node("없는라벨") is None


# ---------------------------------------------------------------- Claude 출력 모델


def test_enrichment_response_parses_from_dict():
    data = {
        "summary": "측정값 이벤트 노드 분리를 권장합니다.",
        "suggestions": [
            {
                "kind": "add_node",
                "target": "측정값",
                "rationale": "시계열 측정을 별도 노드로 분리",
                "payload": {"label": "측정값", "properties": [{"name": "값", "type": "float"}]},
            }
        ],
    }
    resp = EnrichmentResponse.model_validate(data)
    assert len(resp.suggestions) == 1
    assert resp.suggestions[0].kind == "add_node"


def test_suggestion_invalid_kind_rejected():
    with pytest.raises(ValidationError):
        Suggestion(kind="delete_everything", target="x", rationale="y")


# ================================================================
# 코드 검수 반영 — 유니코드 방어선 강화 / key_property 정제 / 엣지케이스
# ================================================================


@pytest.mark.parametrize("cp", [0x0B, 0x1F, 0x7F, 0x85, 0x9F, 0x2028, 0x2029])
def test_c1_and_separator_controls_rejected_in_label(cp):
    # C0/C1 제어, DEL, 줄/문단 구분자를 라벨 내부에 넣으면 거부되어야 함
    with pytest.raises(ValidationError):
        NodeLabel(label="측정" + chr(cp) + "소")


@pytest.mark.parametrize("cp", [0xFF40, 0x200B, 0x202E, 0xFEFF])
def test_confusable_and_zero_width_chars_rejected(cp):
    # 전각 백틱(U+FF40), zero-width space(U+200B), RTL override(U+202E), BOM(U+FEFF)
    with pytest.raises(ValidationError):
        NodeLabel(label="라벨" + chr(cp))


def test_property_name_with_interior_control_rejected():
    # key 우회 차단: 속성명 자체가 원천에서 거부되어야 함
    with pytest.raises(ValidationError):
        PropertyDef(name="코" + chr(0x85) + "드")


def test_key_property_whitespace_is_normalized_and_matched():
    # (H2a) 속성명과 key가 공백만 다를 때 정상 매칭되고, 둘 다 정규화되어야 함
    n = NodeLabel(
        label="측정소",
        properties=[PropertyDef(name="  측정소코드  ")],
        key_property="  측정소코드  ",
    )
    assert n.key_property == "측정소코드"
    assert n.properties[0].name == "측정소코드"


def test_key_property_backtick_rejected():
    # (H2b) key 경로로도 백틱이 새면 안 됨
    with pytest.raises(ValidationError):
        NodeLabel(label="측정소", properties=[PropertyDef(name="c")], key_property="c`")


def test_self_loop_relationship_is_allowed():
    # (:저수지)-[:인접]->(:저수지) 같은 자기루프는 정당한 모델링 → 허용
    schema = OntologySchema(
        nodes=[NodeLabel(label="저수지")],
        relationships=[RelationshipType(type="인접", start_label="저수지", end_label="저수지")],
    )
    assert schema.relationships[0].signature == ("인접", "저수지", "저수지")


def test_empty_schema_is_valid():
    schema = OntologySchema()
    assert schema.nodes == []
    assert schema.relationships == []
    assert schema.labels == set()
    assert schema.consistency_warnings() == []


def test_duplicate_relationship_detected_after_trim():
    # 공백만 다른 동일 관계는 정제 후 중복으로 감지되어야 함
    with pytest.raises(ValidationError):
        OntologySchema(
            nodes=[NodeLabel(label="측정소"), NodeLabel(label="수질항목")],
            relationships=[
                RelationshipType(type="측정", start_label="측정소", end_label="수질항목"),
                RelationshipType(type="  측정  ", start_label="측정소", end_label="수질항목"),
            ],
        )


def test_relationship_duplicate_property_names_rejected():
    with pytest.raises(ValidationError):
        RelationshipType(
            type="측정",
            start_label="측정소",
            end_label="수질항목",
            properties=[PropertyDef(name="정확도"), PropertyDef(name="정확도")],
        )


def test_consistency_warnings_reports_both_kinds():
    schema = OntologySchema(
        nodes=[NodeLabel(label="측정값")],  # key 없음 → missing-key 경고
        relationships=[
            RelationshipType(type="항목", start_label="측정값", end_label="수질항목")  # 미지 라벨
        ],
    )
    warnings = schema.consistency_warnings()
    assert any("수질항목" in w for w in warnings)      # unknown label
    assert any("key_property" in w for w in warnings)  # missing key


@pytest.mark.parametrize("bad_type", ["STRING", "number", "String ", "text", ""])
def test_property_type_literal_is_strict(bad_type):
    with pytest.raises(ValidationError):
        PropertyDef(name="x", type=bad_type)


def test_suggestion_payload_allows_arbitrary_nesting():
    s = Suggestion(
        kind="add_relationship",
        target="측정→수질항목",
        rationale="다대다",
        payload={"nested": {"a": [1, 2, {"b": True}]}, "list": [{"x": 1}]},
    )
    assert s.payload["nested"]["a"][2]["b"] is True
