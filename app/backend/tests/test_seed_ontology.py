"""seed_ontology.py 검증 — 시드가 models.py 규약을 지키는지, 도메인 사실이 반영됐는지."""

from app.models import OntologySchema
from app.seed_ontology import (
    ALGAE_ALERT_THRESHOLDS,
    DOMAIN_GUIDE,
    SEED_ONTOLOGY,
    WATER_QUALITY_ITEMS,
)


def test_seed_is_valid_ontology_schema():
    # 생성 시점에 검증되지만, 재검증으로 회귀 방지
    assert isinstance(SEED_ONTOLOGY, OntologySchema)
    assert OntologySchema.model_validate(SEED_ONTOLOGY.model_dump()) == SEED_ONTOLOGY
    assert len(SEED_ONTOLOGY.nodes) == 8
    assert len(SEED_ONTOLOGY.relationships) == 10


def test_seed_relationships_reference_existing_labels():
    labels = SEED_ONTOLOGY.labels
    for r in SEED_ONTOLOGY.relationships:
        assert r.start_label in labels, f"{r.type} start '{r.start_label}' 누락"
        assert r.end_label in labels, f"{r.type} end '{r.end_label}' 누락"


def test_seed_has_no_unknown_label_warnings():
    unknown = [w for w in SEED_ONTOLOGY.consistency_warnings() if "대응하는 노드 정의가 없습니다" in w]
    assert unknown == []


def test_seed_key_properties_are_declared():
    for n in SEED_ONTOLOGY.nodes:
        if n.key_property is not None:
            assert n.key_property in {p.name for p in n.properties}


def test_measurement_is_event_node_without_key():
    m = SEED_ONTOLOGY.node("측정값")
    assert m is not None
    assert m.key_property is None  # 이벤트 노드는 관계로 정체성 표현


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


def test_seed_missing_key_warnings_are_expected():
    # 이벤트 노드 3개(측정값/조류경보/대응조치)는 key가 없어 경고가 나야 정상.
    # 키가 실수로 추가/삭제되면 이 테스트가 잡아낸다.
    missing_key = [w for w in SEED_ONTOLOGY.consistency_warnings() if "key_property" in w]
    assert len(missing_key) == 3
    for label in ("측정값", "조류경보", "대응조치"):
        assert any(label in w for w in missing_key), f"{label} 경고 누락"
