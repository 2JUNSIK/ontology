"""seed_ontology.py 검증 — 도메인 가이드 상수·임계값이 반영됐는지(claude_extractor가 사용)."""

from app.seed_ontology import (
    ALGAE_ALERT_THRESHOLDS,
    CANONICAL_ALIASES,
    DOMAIN_GUIDE,
    RELATION_CONSTRAINTS,
    STANDARD_ENTITY_TYPES,
    STANDARD_RELATION_TYPES,
    TYPE_ALIASES,
    WATER_QUALITY_ITEMS,
)


def test_alert_thresholds_are_monotonic():
    assert ALGAE_ALERT_THRESHOLDS["관심"] < ALGAE_ALERT_THRESHOLDS["경계"] < ALGAE_ALERT_THRESHOLDS["대발생"]
    assert ALGAE_ALERT_THRESHOLDS["대발생"] == 1_000_000


def test_domain_guide_contains_thresholds_and_items():
    assert "1,000,000" in DOMAIN_GUIDE  # 대발생 임계값
    assert "남조류세포수" in DOMAIN_GUIDE
    assert "이벤트 노드" in DOMAIN_GUIDE


def test_water_quality_items_present():
    names = {n for n, _ in WATER_QUALITY_ITEMS}
    assert {"클로로필-a", "남조류세포수", "T-P", "T-N", "DO"}.issubset(names)


# ---- N9 표준 어휘 정합 ----

def test_relation_constraints_use_standard_types():
    """domain/range 제약의 관계타입·엔티티 타입은 표준 집합의 부분집합이어야 한다."""
    std_types = set(STANDARD_ENTITY_TYPES)
    for rt, (src, tgt) in RELATION_CONSTRAINTS.items():
        assert rt in STANDARD_RELATION_TYPES, rt
        assert src <= std_types, (rt, src - std_types)
        assert tgt <= std_types, (rt, tgt - std_types)


def test_type_aliases_map_to_standard_and_are_nonstandard_keys():
    std_types = set(STANDARD_ENTITY_TYPES)
    for alias, canon in TYPE_ALIASES.items():
        assert canon in std_types, (alias, canon)  # 표준값으로 접힘
        assert alias not in std_types  # 별칭 자신은 비표준(정의 충돌 방지)


def test_canonical_aliases_consistent_with_water_items():
    item_names = {n for n, _ in WATER_QUALITY_ITEMS}
    assert CANONICAL_ALIASES["총인"] == "T-P" and "T-P" in item_names
    assert CANONICAL_ALIASES["총질소"] == "T-N" and "T-N" in item_names


def test_canonical_aliases_targets_not_alias_keys():
    """별칭의 표준값은 다시 별칭 키가 아니어야 한다(정규화 단일 홉·멱등 보장)."""
    keys = set(CANONICAL_ALIASES)
    for v in CANONICAL_ALIASES.values():
        assert v not in keys, v


def test_domain_guide_contains_standard_vocab():
    assert "표준 어휘" in DOMAIN_GUIDE
    assert "저수지" in DOMAIN_GUIDE and "관할" in DOMAIN_GUIDE
