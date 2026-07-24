"""claude_enricher 테스트 — 실제 API 호출 없이(모킹) 매핑/우아한 열화 검증."""

import types

import pytest

from app import claude_enricher as ce
from app.config import settings
from app.models import EnrichmentResponse, OntologySchema


def test_enrich_returns_empty_without_api_key():
    # conftest가 키를 비워둠 → 실제 호출 없이 빈 응답
    result = ce.enrich(OntologySchema(), {}, "자유서술")
    assert isinstance(result, EnrichmentResponse)
    assert result.suggestions == []
    assert result.summary == ""


# ---------------------------------------------------------------- 매핑 로직


def test_map_add_node_revalidates_payload():
    out = ce._EnrichmentOut(
        summary="측정값 분리 권장",
        suggestions=[
            ce._SuggestionOut(
                kind="add_node", target="측정값", rationale="시계열 이벤트 분리",
                node_label="측정값",
                key_property=None,
                properties=[ce._PropOut(name="값", type="float", required=True)],
            )
        ],
    )
    resp = ce._map_to_internal(out)
    assert len(resp.suggestions) == 1
    s = resp.suggestions[0]
    assert s.kind == "add_node"
    assert s.payload["label"] == "측정값"
    assert s.payload["properties"][0]["name"] == "값"


def test_map_add_relationship():
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(
            kind="add_relationship", target="측정→수질항목", rationale="측정소가 항목을 측정",
            relationship_type="측정", start_label="측정소", end_label="수질항목",
        )
    ])
    resp = ce._map_to_internal(out)
    assert resp.suggestions[0].payload["type"] == "측정"
    assert resp.suggestions[0].payload["start_label"] == "측정소"


def test_map_invalid_identifier_is_downgraded_to_warning():
    # 백틱이 든 라벨은 코어 모델 검증에서 걸려 경고로 강등되어야 함(§5 방어선)
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(
            kind="add_node", target="악성", rationale="주입 시도",
            node_label="측정소`) DROP //",
        )
    ])
    resp = ce._map_to_internal(out)
    assert len(resp.suggestions) == 1
    assert resp.suggestions[0].kind == "warning"
    assert resp.suggestions[0].payload == {}


def test_map_warning_kind_passthrough():
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(kind="warning", target="측정소-수질항목", rationale="관계 누락 의심")
    ])
    resp = ce._map_to_internal(out)
    assert resp.suggestions[0].kind == "warning"
    assert resp.suggestions[0].payload == {}


def test_add_property_target_label_is_sanitized():
    # (H1) 정상 target_label은 정제되어 payload에 담김
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(
            kind="add_property", target="측정소.정확도", rationale="정확도 속성 추가",
            node_label="  측정소  ",
            properties=[ce._PropOut(name="정확도", type="float")],
        )
    ])
    resp = ce._map_to_internal(out)
    assert resp.suggestions[0].kind == "add_property"
    assert resp.suggestions[0].payload["target_label"] == "측정소"  # trim/정제됨
    assert resp.suggestions[0].payload["name"] == "정확도"


def test_add_property_injected_target_label_downgraded():
    # (H1 회귀) 백틱 든 node_label은 정제에서 걸려 warning으로 강등, payload 비움
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(
            kind="add_property", target="악성", rationale="주입",
            node_label="측정소`) DROP CONSTRAINT //",
            properties=[ce._PropOut(name="x")],
        )
    ])
    resp = ce._map_to_internal(out)
    assert resp.suggestions[0].kind == "warning"
    assert resp.suggestions[0].payload == {}


def test_add_relationship_missing_endpoint_downgraded():
    # (L2) kind는 add_relationship인데 end_label 누락 → warning 강등
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(
            kind="add_relationship", target="측정", rationale="누락",
            relationship_type="측정", start_label="측정소",  # end_label 없음
        )
    ])
    resp = ce._map_to_internal(out)
    assert resp.suggestions[0].kind == "warning"


def test_add_node_key_not_in_properties_downgraded():
    # key_property가 properties에 없으면 NodeLabel 검증 실패 → warning 강등
    out = ce._EnrichmentOut(suggestions=[
        ce._SuggestionOut(
            kind="add_node", target="측정소", rationale="키 불일치",
            node_label="측정소", key_property="측정소코드",
            properties=[ce._PropOut(name="명칭")],
        )
    ])
    resp = ce._map_to_internal(out)
    assert resp.suggestions[0].kind == "warning"


def test_stable_prefix_is_deterministic():
    # 캐시 무효화 방지: 프리픽스는 호출마다 바이트 동일해야 함
    assert ce._stable_prefix() == ce._stable_prefix()


# ---------------------------------------------------------------- 모킹된 end-to-end


def test_enrich_with_mocked_client(monkeypatch):
    # 더미 키로 활성화하되, 클라이언트는 가짜로 대체(실제 호출 없음)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-dummy", raising=False)

    captured = {}

    fake_out = ce._EnrichmentOut(
        summary="ok",
        suggestions=[ce._SuggestionOut(kind="warning", target="x", rationale="y")],
    )

    def fake_parse(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(parsed_output=fake_out)

    fake_client = types.SimpleNamespace(
        messages=types.SimpleNamespace(parse=fake_parse)
    )
    monkeypatch.setattr(ce, "_make_client", lambda: fake_client)

    resp = ce.enrich(OntologySchema(), {"free_text": "측정값이 매일 쌓인다"}, "측정값이 매일 쌓인다")
    assert resp.summary == "ok"
    assert resp.suggestions[0].kind == "warning"

    # prompt caching 배선 검증: system 프리픽스에 cache_control 이 있어야 함
    system = captured["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert "시드 온톨로지" in system[0]["text"]
    assert captured["model"] == settings.anthropic_model
    # 가변부(자유서술/draft)는 user 턴에만
    assert "측정값이 매일 쌓인다" in captured["messages"][0]["content"]


def test_enrich_swallows_exceptions(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-dummy", raising=False)

    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(ce, "_make_client", boom)
    # 예외가 나도 빈 응답으로 열화(draft 흐름 보존)
    resp = ce.enrich(OntologySchema(), {}, "")
    assert resp.suggestions == []


def test_enrich_handles_none_parsed_output(monkeypatch):
    # refusal/max_tokens 로 parsed_output=None 이면 빈 응답
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-dummy", raising=False)

    def fake_parse(**kwargs):
        return types.SimpleNamespace(parsed_output=None)

    fake_client = types.SimpleNamespace(messages=types.SimpleNamespace(parse=fake_parse))
    monkeypatch.setattr(ce, "_make_client", lambda: fake_client)

    resp = ce.enrich(OntologySchema(), {}, "")
    assert resp.suggestions == []
    assert resp.summary == ""
