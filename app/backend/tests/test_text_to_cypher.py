"""text_to_cypher 단위테스트 (실제 Claude 호출 없음).

conftest가 ANTHROPIC_API_KEY를 공백화하므로 키 없는 경로는 호출 없이 None으로 열화한다.
Claude 경로는 _make_client를 모킹해 SDK 호출 형태(system cache_control, output_format,
user 턴에 질문/힌트)를 검증한다.
"""

from app import text_to_cypher
from app.config import settings
from app.text_to_cypher import _QueryOut, generate_query


def test_generate_no_key_returns_none():
    # conftest가 키 공백화 → 실제 호출 없이 None
    assert generate_query("녹조와 연결된 노드 보여줘") is None


def test_generate_empty_question_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)
    assert generate_query("   ") is None


class _FakeResp:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _FakeMessages:
    def __init__(self, parsed, calls):
        self._parsed = parsed
        self._calls = calls

    def parse(self, **kwargs):
        self._calls.append(kwargs)
        return _FakeResp(self._parsed)


class _FakeClient:
    def __init__(self, parsed, calls):
        self.messages = _FakeMessages(parsed, calls)


def test_generate_with_mocked_client(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)
    parsed = _QueryOut(
        cypher="MATCH (n:`_Entity` {_project:$pid}) RETURN n LIMIT 100",
        explanation="이 프로젝트의 모든 노드를 조회합니다",
        result_kind="graph",
    )
    calls: list = []
    monkeypatch.setattr(text_to_cypher, "_make_client", lambda: _FakeClient(parsed, calls))

    out = generate_query(
        "모든 노드 보여줘", types=["현상"], rel_types=["원인"], entity_names=["녹조"]
    )
    assert out is not None
    assert out.cypher.startswith("MATCH")
    assert out.result_kind == "graph"

    # SDK 호출 형태 검증(1회 호출)
    assert len(calls) == 1
    kw = calls[0]
    assert kw["model"] == settings.anthropic_model
    assert kw["output_format"] is _QueryOut
    # 안정 프리픽스에 cache_control
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    # 질문/힌트는 user 턴(가변부)에 실린다
    user_text = kw["messages"][0]["content"]
    assert "모든 노드 보여줘" in user_text
    assert "현상" in user_text and "원인" in user_text and "녹조" in user_text


def test_generate_api_failure_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)

    def _raise():
        raise RuntimeError("network down")

    monkeypatch.setattr(text_to_cypher, "_make_client", _raise)
    assert generate_query("질문") is None


def test_generate_parsed_none_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)
    calls: list = []
    monkeypatch.setattr(text_to_cypher, "_make_client", lambda: _FakeClient(None, calls))
    assert generate_query("질문") is None
