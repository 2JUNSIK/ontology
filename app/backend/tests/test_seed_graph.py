"""seed_graph 단위테스트 — 표준 시드 온톨로지(N15)의 무결성.

DB 접근 없음. 시드가 (1) 표준 어휘만 사용, (2) domain/range 무경고, (3) 끊긴 엣지 없음,
(4) 정량 속성 유효·상수 일치, (5) 정규화 후에도 손실 없음, (6) 결정적·인젝션 안전을 검증한다.
"""

from app.cypher_builder import build_ingest_statements
from app.models import Entity, Extraction
from app.ontology_normalizer import canonicalize_extraction, validate_domain_range
from app.seed_graph import build_seed_extraction
from app.seed_ontology import (
    ALGAE_ALERT_THRESHOLDS,
    STANDARD_ENTITY_TYPES,
    STANDARD_RELATION_TYPES,
)


def test_returns_nonempty_extraction():
    seed = build_seed_extraction()
    assert isinstance(seed, Extraction)
    assert len(seed.entities) > 0
    assert len(seed.relations) > 0
    # 이름은 프로젝트 내 정체성 → 중복 정의가 없어야 한다(정의 1회)
    names = [e.name for e in seed.entities]
    assert len(names) == len(set(names)), "시드 엔티티 이름이 중복 정의됨"


def test_all_entity_types_are_standard():
    seed = build_seed_extraction()
    allowed = set(STANDARD_ENTITY_TYPES)
    for e in seed.entities:
        assert e.type in allowed, f"비표준 타입: {e.type} ({e.name})"


def test_all_relation_types_are_standard():
    seed = build_seed_extraction()
    allowed = set(STANDARD_RELATION_TYPES)
    for r in seed.relations:
        assert r.type in allowed, f"비표준 관계타입: {r.type}"


def test_relation_endpoints_exist_as_entities():
    seed = build_seed_extraction()
    names = {e.name for e in seed.entities}
    for r in seed.relations:
        assert r.source in names, f"끊긴 출발점: {r.source}"
        assert r.target in names, f"끊긴 도착점: {r.target}"


def test_no_domain_range_warnings():
    # 시드는 도메인/레인지 제약을 완전히 만족해야 한다(교육 자료로서 모범이어야 하므로).
    assert validate_domain_range(build_seed_extraction()) == []


def test_no_reserved_prefix_labels():
    seed = build_seed_extraction()
    for e in seed.entities:
        assert not e.type.startswith("_")


def test_alert_stage_quantities_match_constant():
    seed = build_seed_extraction()
    by_name = {e.name: e for e in seed.entities}
    for stage, threshold in ALGAE_ALERT_THRESHOLDS.items():
        e = by_name[stage]
        assert e.type == "경보단계"
        assert e.value == float(threshold)
        assert e.unit == "cells/mL"
        assert e.comparator == ">="


def test_deterministic():
    a = build_seed_extraction()
    b = build_seed_extraction()
    assert a.model_dump() == b.model_dump()


def test_canonicalize_is_noop_and_preserves_quantities():
    """시드는 이미 표준 어휘라 정규화가 사실상 no-op이어야 한다(엔티티/관계 수·이름 보존).
    정량 속성도 보존돼야 한다(정규화 버그 회귀 방지)."""
    seed = build_seed_extraction()
    norm = canonicalize_extraction(seed)
    assert [e.name for e in norm.entities] == [e.name for e in seed.entities]
    assert len(norm.relations) == len(seed.relations)
    by_name = {e.name: e for e in norm.entities}
    for stage, threshold in ALGAE_ALERT_THRESHOLDS.items():
        assert by_name[stage].value == float(threshold)
        assert by_name[stage].unit == "cells/mL"


def test_ingestable_without_error():
    """시드가 cypher_builder 방어선(인젝션·식별자 검증)을 통과해 ingest 문으로 변환된다."""
    seed = build_seed_extraction()
    stmts = build_ingest_statements("test_project", seed)
    assert len(stmts) > 0
    # 엔티티 MERGE·관계 문이 모두 생성되고, 정량 속성 SET이 포함된다.
    kinds = {s.kind for s in stmts}
    assert "entity_merge" in kinds
    assert "relation" in kinds
    merge = next(s for s in stmts if s.kind == "entity_merge")
    assert "n.value" in merge.cypher
    # 임계값이 파라미터로 바인딩된다(식별자 위치에 값 삽입 금지 — 인젝션 안전).
    values = {row["value"] for row in merge.params["rows"] if row["value"] is not None}
    for threshold in ALGAE_ALERT_THRESHOLDS.values():
        assert float(threshold) in values
