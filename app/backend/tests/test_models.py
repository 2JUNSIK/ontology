"""models.py 엣지케이스 테스트 (설계 불변식 §1·§3 검증).

v2 지식그래프 모델(Entity/Relation/Extraction)과 이들이 공유하는 인젝션 방어선
(_clean_value=값 / _clean_label_or_type=식별자)을 검증한다. 이름/설명은 값(파라미터
바인딩, 백틱 허용), 타입 라벨/관계타입은 식별자(백틱·제어문자·'_'프리픽스 거부)다.
"""

import unicodedata

import pytest
from pydantic import ValidationError

from app.models import Entity, Extraction, Relation

# ---------------------------------------------------------------- 정상 / round-trip


def test_entity_defaults():
    e = Entity(name="녹조")
    assert e.type == ""  # 미분류 허용
    assert e.description == ""


def test_entity_trims_and_normalizes_whitespace():
    e = Entity(name="  녹조  ", type="  현상  ")
    assert e.name == "녹조"
    assert e.type == "현상"


def test_extraction_roundtrip():
    ext = Extraction(
        entities=[
            Entity(name="녹조", type="현상", description="남조류 과다 증식"),
            Entity(name="남조류", type="생물"),
        ],
        relations=[Relation(source="녹조", target="남조류", type="원인")],
        summary="요약",
    )
    dumped = ext.model_dump()
    assert Extraction.model_validate(dumped) == ext


def test_empty_extraction_is_valid():
    ext = Extraction()
    assert ext.entities == []
    assert ext.relations == []
    assert ext.summary == ""


# ---------------------------------------------------------------- 값(name) 방어선: _clean_value


@pytest.mark.parametrize("bad", ["", "   ", "\t\n"])
def test_entity_name_required_nonempty(bad):
    with pytest.raises(ValidationError):
        Entity(name=bad)


def test_entity_name_rejects_control_char():
    with pytest.raises(ValidationError):
        Entity(name="a\tb")


def test_entity_name_allows_backtick_as_value():
    # 이름은 값(파라미터 바인딩) — 백틱 허용(식별자와 달리).
    assert Entity(name="a`b").name == "a`b"


def test_entity_name_length_boundary():
    Entity(name="a" * 500)  # 경계값 OK
    with pytest.raises(ValidationError):
        Entity(name="a" * 501)


def test_relation_endpoints_reject_control_char():
    with pytest.raises(ValidationError):
        Relation(source="A\x00", target="B", type="rel")
    with pytest.raises(ValidationError):
        Relation(source="A", target="B\x00C", type="rel")  # 내부 제어문자(비공백)


# ---------------------------------------------------------------- 식별자(type) 방어선: _clean_label_or_type


def test_entity_empty_type_allowed():
    assert Entity(name="x", type="   ").type == ""
    assert Entity(name="x").type == ""


def test_relation_type_required_nonempty():
    with pytest.raises(ValidationError):
        Relation(source="A", target="B", type="   ")


def test_backtick_in_type_rejected():
    # DDL 인젝션 1차 방어선: 식별자엔 백틱 금지(값과 달리)
    with pytest.raises(ValidationError):
        Entity(name="x", type="현상`) DETACH DELETE n //")
    with pytest.raises(ValidationError):
        Relation(source="A", target="B", type="원인`")


def test_control_char_in_type_rejected():
    with pytest.raises(ValidationError):
        Entity(name="x", type="현\x00상")


def test_too_long_type_rejected():
    with pytest.raises(ValidationError):
        Entity(name="x", type="현" * 101)


@pytest.mark.parametrize("cp", [0x0B, 0x1F, 0x7F, 0x85, 0x9F, 0x2028, 0x2029])
def test_c1_and_separator_controls_rejected_in_type(cp):
    # C0/C1 제어, DEL, 줄/문단 구분자를 타입 라벨에 넣으면 거부되어야 함
    with pytest.raises(ValidationError):
        Entity(name="x", type="현" + chr(cp) + "상")


@pytest.mark.parametrize("cp", [0xFF40, 0x200B, 0x202E, 0xFEFF])
def test_confusable_and_zero_width_chars_rejected_in_type(cp):
    # 전각 백틱(U+FF40), zero-width space(U+200B), RTL override(U+202E), BOM(U+FEFF)
    with pytest.raises(ValidationError):
        Entity(name="x", type="현상" + chr(cp))


@pytest.mark.parametrize("bad", ["_Entity", "_Project", "_hidden"])
def test_underscore_prefixed_type_rejected(bad):
    # '_' 프리픽스는 내부/메타 예약 → 사용자 타입 라벨/관계타입 금지
    with pytest.raises(ValidationError):
        Entity(name="x", type=bad)
    with pytest.raises(ValidationError):
        Relation(source="A", target="B", type=bad)


def test_type_is_nfc_normalized():
    # NFD로 갈라진 같은 글자가 NFC로 합쳐져 저장되어야(중복 라벨 방지)
    nfc = "각"  # U+AC01
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc  # 입력은 분해형
    assert Entity(name="x", type=nfd).type == nfc
    assert Relation(source="A", target="B", type=nfd).type == nfc


# ---------------------------------------------------------------- 값(name) 방어선 대칭 보강


def test_name_is_nfc_normalized():
    # 이름도 NFC로 정규화되어야 같은 개념이 서로 다른 코드포인트로 갈라지지 않고 MERGE 병합됨
    nfc = "각"  # U+AC01
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc
    assert Entity(name=nfd).name == nfc
    assert Relation(source=nfd, target="B", type="rel").source == nfc
    assert Relation(source="A", target=nfd, type="rel").target == nfc


@pytest.mark.parametrize("cp", [0x200B, 0x202E, 0xFEFF, 0x2028, 0x2029, 0x9F, 0x1F])
def test_zero_width_and_controls_rejected_in_name(cp):
    # 값 경로(_clean_value)도 식별자와 동일하게 zero-width/RTL/C1/구분자를 내부에서 거부
    with pytest.raises(ValidationError):
        Entity(name="녹" + chr(cp) + "조")
    with pytest.raises(ValidationError):
        Relation(source="A", target="B" + chr(cp) + "C", type="rel")


def test_description_is_free_text_no_validator():
    # description은 값(파라미터 바인딩)이며 validator가 없다 — 백틱·장문을 그대로 보존한다.
    # (누군가 실수로 description에 검증기를 붙이면 이 테스트가 잡아낸다.)
    injectionish = "a`b) DETACH DELETE n //"
    long_text = "설명 " * 400  # >500자(값 길이 제한을 적용받지 않음)
    assert Entity(name="x", description=injectionish).description == injectionish
    assert Entity(name="x", description=long_text).description == long_text
    r = Relation(source="A", target="B", type="rel", description=injectionish)
    assert r.description == injectionish
