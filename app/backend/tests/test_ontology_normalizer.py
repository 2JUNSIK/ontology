"""ontology_normalizer 단위테스트 — 순수 함수(별칭·타입 정규화, domain/range 검증).

DB 접근 없음. 멱등성·순수성·표준화·경고 정책(관대 통과·삭제 없음)을 검증한다.
"""

from app.models import Entity, Extraction, Relation
from app.ontology_normalizer import (
    canonical_name,
    canonical_type,
    canonicalize_extraction,
    validate_domain_range,
)


def test_canonical_name_maps_alias():
    assert canonical_name("총인") == "T-P"
    assert canonical_name("시아노박테리아") == "남조류"
    # 별칭이 아니면 정제된 원문 그대로(NFC+trim)
    assert canonical_name("녹조") == "녹조"
    assert canonical_name("  녹조  ") == "녹조"


def test_canonical_type_maps_alias_and_keeps_unknown():
    assert canonical_type("관측소") == "측정소"
    assert canonical_type("현상") == "현상"  # 표준 → 유지
    assert canonical_type("우주정거장") == "우주정거장"  # 비표준 → 관대 통과(드롭 아님)
    assert canonical_type("") == ""


def test_canonicalize_merges_alias_entities():
    ext = Extraction(
        entities=[
            Entity(name="조류대발생", type="현상", description=""),
            Entity(name="녹조", type="", description="물이 녹색"),
        ],
        relations=[],
    )
    out = canonicalize_extraction(ext)
    # 조류대발생 → 녹조로 접혀 하나로 병합(등장 순서 보존)
    assert [e.name for e in out.entities] == ["녹조"]
    e = out.entities[0]
    assert e.type == "현상"  # 타입: non-empty 우선(먼저 등장)
    assert e.description == "물이 녹색"  # 설명: non-empty 우선


def test_canonicalize_rewrites_relation_endpoints():
    ext = Extraction(
        entities=[Entity(name="녹조", type="현상")],
        relations=[Relation(source="조류대발생", target="남조류", type="원인")],
    )
    out = canonicalize_extraction(ext)
    r = out.relations[0]
    assert r.source == "녹조"  # 끝점도 표준명으로 치환(끊긴 엣지 방지)
    assert r.target == "남조류"


def test_canonicalize_dedups_relations():
    ext = Extraction(
        entities=[],
        relations=[
            Relation(source="조류대발생", target="남조류", type="원인", description=""),
            Relation(source="녹조", target="남조류", type="원인", description="설명"),
        ],
    )
    out = canonicalize_extraction(ext)
    assert len(out.relations) == 1
    assert out.relations[0].description == "설명"  # non-empty 우선


def test_canonicalize_is_idempotent():
    ext = Extraction(
        entities=[Entity(name="총인", type="관측소")],
        relations=[Relation(source="조류대발생", target="총인", type="측정")],
    )
    once = canonicalize_extraction(ext)
    twice = canonicalize_extraction(once)
    assert once.model_dump() == twice.model_dump()


def test_canonicalize_does_not_mutate_input():
    ext = Extraction(entities=[Entity(name="총인", type="")], relations=[])
    _ = canonicalize_extraction(ext)
    assert ext.entities[0].name == "총인"  # 입력 불변(새 객체 반환)


def test_validate_domain_range_flags_violation():
    # 측정소가 저수지로 '유입'된다 → 유입: (오염원)→(수체) 위반(출발 타입 오류)
    ext = Extraction(
        entities=[
            Entity(name="A측정소", type="측정소"),
            Entity(name="어떤저수지", type="저수지"),
        ],
        relations=[Relation(source="A측정소", target="어떤저수지", type="유입")],
    )
    warnings = validate_domain_range(ext)
    assert len(warnings) == 1
    assert "유입" in warnings[0]


def test_merge_entity_type_conflict_first_wins():
    """같은 canonical 이름에 서로 다른 non-empty 타입 → 먼저 등장 우선(결정적, 문서화된 동작).
    Entity.type이 단수라 둘째 타입은 버려진다(모델 한계) — 회귀 시 침묵하지 않도록 못 박는다."""
    ext = Extraction(
        entities=[
            Entity(name="녹조", type="현상"),
            Entity(name="조류대발생", type="생물"),  # → 녹조로 접힘
        ],
        relations=[],
    )
    out = canonicalize_extraction(ext)
    assert [e.name for e in out.entities] == ["녹조"]
    assert out.entities[0].type == "현상"  # 먼저 등장 우선


def test_canonical_name_nfd_input():
    """NFD로 들어온 별칭 키도 매칭돼야 한다(사전은 NFC 키, 조회 시 NFC 정규화)."""
    import unicodedata

    nfd = unicodedata.normalize("NFD", "총인")
    assert nfd != "총인"
    assert canonical_name(nfd) == "T-P"


def test_canonical_name_case_sensitive_aliases():
    """대소문자 변형 별칭은 사전에 명시된 것만 접힌다(임의 소문자화 안 함)."""
    assert canonical_name("클로로필a") == "클로로필-a"
    assert canonical_name("클로로필A") == "클로로필-a"


def test_canonicalize_collapses_to_self_loop_and_dedups():
    """별칭 붕괴로 두 관계가 동일 self-loop가 되면 dedup 1개(첫 설명 유지)."""
    ext = Extraction(
        entities=[Entity(name="녹조", type="현상")],
        relations=[
            Relation(source="조류대발생", target="녹조", type="원인", description="A"),
            Relation(source="녹조", target="녹조", type="원인", description=""),
        ],
    )
    out = canonicalize_extraction(ext)
    assert len(out.relations) == 1
    assert out.relations[0].source == out.relations[0].target == "녹조"
    assert out.relations[0].description == "A"


def test_validate_domain_range_ok_and_unknown_pass():
    ext = Extraction(
        entities=[
            Entity(name="축산폐수", type="오염원"),
            Entity(name="대청호", type="저수지"),
            Entity(name="미상", type=""),  # 타입 미상
        ],
        relations=[
            Relation(source="축산폐수", target="대청호", type="유입"),  # 정상
            Relation(source="미상", target="대청호", type="유입"),  # source 타입 미상 → 통과
            Relation(source="축산폐수", target="대청호", type="자유관계"),  # 제약 없는 관계 → 통과
        ],
    )
    assert validate_domain_range(ext) == []
