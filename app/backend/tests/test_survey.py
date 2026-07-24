"""survey.py 테스트 — 문항 구조 + 답변→draft 규칙(순수 함수)."""

from types import MappingProxyType

import pytest

from app.models import OntologySchema, PropertyDef
from app.survey import QUESTIONS, build_draft, selected_labels

# ---------------------------------------------------------------- 문항 구조


def test_questions_have_unique_ids():
    ids = [q.id for q in QUESTIONS]
    assert len(ids) == len(set(ids))


def test_expected_question_ids_present():
    ids = {q.id for q in QUESTIONS}
    assert ids == {
        "assets", "has_station", "water_items", "algae_alert",
        "pollution_sources", "measures", "organizations", "free_text",
    }


def test_choice_questions_have_options_text_question_has_none():
    for q in QUESTIONS:
        if q.type in ("single", "multi"):
            assert q.options, f"{q.id} 선택형인데 옵션 없음"
        else:  # text
            assert q.options == []


# ---------------------------------------------------------------- build_draft 규칙


def test_empty_answers_yield_empty_draft():
    draft = build_draft({})
    assert isinstance(draft, OntologySchema)
    assert draft.nodes == []
    assert draft.relationships == []


def test_reservoir_only():
    draft = build_draft({"assets": ["저수지"]})
    assert draft.labels == {"저수지"}
    assert draft.relationships == []


def test_station_requires_yes():
    assert "측정소" not in build_draft({"has_station": "아니오"}).labels
    assert "측정소" in build_draft({"has_station": "예"}).labels


def test_reservoir_and_station_connects_location_rel():
    draft = build_draft({"assets": ["저수지"], "has_station": "예"})
    assert draft.labels == {"저수지", "측정소"}
    sigs = {r.signature for r in draft.relationships}
    assert ("위치", "측정소", "저수지") in sigs


def test_water_items_add_quality_item_and_measure_rel():
    draft = build_draft({"has_station": "예", "water_items": ["클로로필-a", "남조류세포수"]})
    assert {"측정소", "수질항목"}.issubset(draft.labels)
    sigs = {r.signature for r in draft.relationships}
    assert ("측정", "측정소", "수질항목") in sigs


def test_measurement_event_node_is_never_added_by_rules():
    # 측정값 이벤트 노드는 규칙으로 넣지 않는다 (Claude 보강이 제안하도록 남김).
    draft = build_draft({
        "assets": ["저수지"], "has_station": "예",
        "water_items": ["클로로필-a"], "algae_alert": "예",
        "pollution_sources": ["점오염원"], "measures": ["살수"],
        "organizations": ["유역환경청"],
    })
    assert "측정값" not in draft.labels
    # 측정값이 없으므로 항목/관측지점 관계도 없어야 함
    types = {r.type for r in draft.relationships}
    assert "항목" not in types
    assert "관측지점" not in types


def test_full_selection_yields_seven_nodes_and_expected_rels():
    draft = build_draft({
        "assets": ["저수지"], "has_station": "예",
        "water_items": ["클로로필-a"], "algae_alert": "예",
        "pollution_sources": ["점오염원", "비점오염원"], "measures": ["살수", "조류제거선"],
        "organizations": ["유역환경청", "지자체"],
    })
    assert draft.labels == {"저수지", "측정소", "수질항목", "조류경보", "오염원", "대응조치", "기관"}
    sigs = {r.signature for r in draft.relationships}
    # 양 끝이 모두 선택된 관계만 (측정값 관련 제외) → 8개
    assert ("근거지표", "조류경보", "수질항목") in sigs
    assert ("시행", "기관", "대응조치") in sigs
    assert len(draft.relationships) == 8


def test_pollution_none_selected_no_source_node():
    assert "오염원" not in build_draft({"pollution_sources": []}).labels


def test_answers_accept_string_or_list():
    # water_items 를 문자열 하나로 줘도 동작
    draft = build_draft({"has_station": "예", "water_items": "DO"})
    assert "수질항목" in draft.labels


def test_unknown_answer_keys_are_ignored():
    draft = build_draft({"assets": ["저수지"], "hobby": "낚시", "": None})
    assert draft.labels == {"저수지"}


def test_selected_labels_is_pure_no_mutation():
    answers = {"assets": ["저수지"]}
    a = selected_labels(answers)
    b = selected_labels(answers)
    assert a == b == {"저수지"}
    assert answers == {"assets": ["저수지"]}  # 입력 불변


# ---------------------------------------------------------------- 검수 반영(H1/L4 등)


def test_build_draft_does_not_alias_seed():
    # (H1 회귀) draft 노드를 수정해도 전역 시드가 오염되지 않아야 함
    d1 = build_draft({"assets": ["저수지"]})
    node = d1.node("저수지")
    before = len(node.properties)
    node.properties.append(PropertyDef(name="__leak__"))
    d2 = build_draft({"assets": ["저수지"]})
    assert len(d2.node("저수지").properties) == before


@pytest.mark.parametrize("answers", [
    {"assets": {"저수지": 1}},   # dict 값
    {"assets": True},            # bool
    {"has_station": 1},          # int (예/아니오 아님)
    {"water_items": True},       # bool
])
def test_answer_value_types_are_robust(answers):
    # 이상 타입이어도 예외 없이 처리되고, 라벨을 잘못 만들지 않아야 함
    draft = build_draft(answers)
    assert isinstance(draft, OntologySchema)
    assert draft.labels == set()


def test_has_station_whitespace_is_trimmed():
    assert "측정소" in build_draft({"has_station": " 예 "}).labels


def test_pollution_junk_value_makes_no_node():
    assert "오염원" not in build_draft({"pollution_sources": ["<script>"]}).labels


def test_input_mapping_not_mutated_full():
    answers = {
        "assets": ["저수지"], "has_station": "예", "water_items": ["DO"],
        "algae_alert": "예", "pollution_sources": ["점오염원"],
        "measures": ["살수"], "organizations": ["지자체"],
    }
    snapshot = {k: (list(v) if isinstance(v, list) else v) for k, v in answers.items()}
    build_draft(answers)
    assert answers == snapshot


def test_selected_labels_accepts_generic_mapping():
    labels = selected_labels(MappingProxyType({"assets": ["저수지"]}))
    assert labels == {"저수지"}
