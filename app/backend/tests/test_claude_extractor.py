"""claude_extractor 단위테스트 (실제 Claude 호출 없음).

conftest가 ANTHROPIC_API_KEY를 공백화하므로 extract는 호출 없이 우아하게 열화한다.
매핑(_to_internal)의 식별자 방어선 드롭 동작을 검증한다.
"""

from app.claude_extractor import (
    _EntityOut,
    _ExtractionOut,
    _RelationOut,
    _to_internal,
    extract,
)
from app.models import Extraction


def test_extract_no_key_returns_empty():
    # conftest가 키를 공백화 → 실제 호출 없이 빈 결과
    out = extract("녹조는 남조류가 증식하는 현상이다")
    assert isinstance(out, Extraction)
    assert out.entities == [] and out.relations == []


def test_extract_empty_text_returns_empty(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "dummy", raising=False)
    # 빈/공백 텍스트 → 네트워크 호출 전에 빈 결과
    assert extract("   ").entities == []


def test_to_internal_drops_invalid_identifiers():
    out = _ExtractionOut(
        entities=[
            _EntityOut(name="녹조", type="현상"),
            _EntityOut(name="x", type="_bad"),  # '_' 프리픽스 라벨 → 드롭
            _EntityOut(name="   ", type="생물"),  # 빈 이름 → 드롭
        ],
        relations=[
            _RelationOut(source="녹조", type="원인", target="남조류"),
            _RelationOut(source="녹조", type="   ", target="남조류"),  # 빈 관계타입 → 드롭
        ],
    )
    ext = _to_internal(out)
    assert {e.name for e in ext.entities} == {"녹조"}
    assert len(ext.relations) == 1
    assert ext.relations[0].type == "원인"


def test_to_internal_preserves_valid_type_and_desc():
    out = _ExtractionOut(
        entities=[_EntityOut(name="관심", type="경보단계", description="1000 이상")],
        relations=[],
        summary="요약",
    )
    ext = _to_internal(out)
    assert ext.entities[0].type == "경보단계"
    assert ext.entities[0].description == "1000 이상"
    assert ext.summary == "요약"


def test_to_internal_canonicalizes_aliases():
    """_to_internal이 표준 어휘 정규화(별칭→표준명, 타입 별칭, 관계 끝점)를 적용한다."""
    out = _ExtractionOut(
        entities=[
            _EntityOut(name="조류대발생", type="현상"),
            _EntityOut(name="총인", type="관측소"),  # 이름 별칭 총인→T-P, 타입 별칭 관측소→측정소
        ],
        relations=[_RelationOut(source="조류대발생", type="원인", target="남조류")],
    )
    ext = _to_internal(out)
    names = {e.name for e in ext.entities}
    assert "녹조" in names and "조류대발생" not in names  # 이름 별칭 접힘
    assert "T-P" in names
    assert ext.relations[0].source == "녹조"  # 관계 끝점도 표준명
    tp = next(e for e in ext.entities if e.name == "T-P")
    assert tp.type == "측정소"  # 타입 별칭 접힘
