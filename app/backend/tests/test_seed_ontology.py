"""seed_ontology.py 검증 — 도메인 가이드 상수·임계값이 반영됐는지(claude_extractor가 사용)."""

from app.seed_ontology import (
    ALGAE_ALERT_THRESHOLDS,
    DOMAIN_GUIDE,
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
