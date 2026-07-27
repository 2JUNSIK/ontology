"""공통 중간표현 (Single Source of Truth).

Claude 추출(claude_extractor) · Neo4j 반영(cypher_builder) · 프론트(types.ts)가 모두
공유하는 지식그래프 표현. 새 필드는 반드시 이 모델에서 시작해 양쪽으로 전파한다.
(설계 불변식 §1 — CLAUDE.md 참조)

핵심 구분:
- **이름/설명은 '값'** → Cypher에 파라미터($param)로만 바인딩된다. 백틱을 허용하되
  제어/포맷/구분자 문자는 거부하고 길이만 제한한다(`_clean_value`).
- **타입 라벨/관계타입은 '식별자'** → Cypher DDL/패턴에 삽입되므로 `_clean_label_or_type`로
  검증(백틱·제어문자·'_' 프리픽스 거부)하고, cypher_builder(불변식 §3)가 백틱 이스케이프한다.
- 라벨/이름에 한글을 허용한다(예: "측정소", "녹조"). Neo4j에서 백틱으로 감싸면 유효한
  식별자다. 따라서 ASCII로 제한하지 않는다.
"""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel, Field, field_validator

_MAX_IDENT_LEN = 100

# 식별자에서 거부하는 유니코드 일반 카테고리:
#   Cc 제어, Cf 포맷(zero-width·RTL override 등), Cs 서로게이트,
#   Co 사용자영역, Cn 미할당, Zl 줄구분, Zp 문단구분
# → 백틱으로 감싸도 생성되는 Cypher DDL/스크립트/로그를 깨거나 인젝션 표면을 만든다.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
_BACKTICKS = ("`", "｀")  # ASCII 백틱 + 전각 백틱(｀) 모두 금지


def _clean_identifier(value: str, kind: str) -> str:
    """라벨/관계타입 공통 정제·검증. 정제(NFC + trim)된 문자열을 돌려준다.

    DDL 인젝션의 1차 방어선(설계 불변식 §3). cypher_builder가 백틱 이스케이프로 2차
    방어를 하지만, 여기서 위험 문자(제어/포맷/구분자/백틱)를 먼저 거부한다.
    """
    if not isinstance(value, str):
        raise ValueError(f"{kind}은(는) 문자열이어야 합니다: {value!r}")
    # NFC 정규화 후 앞뒤 공백(유니코드 공백 포함) 제거
    v = unicodedata.normalize("NFC", value).strip()
    if not v:
        raise ValueError(f"{kind}은(는) 비어 있을 수 없습니다")
    if any(b in v for b in _BACKTICKS):
        # 백틱은 Neo4j 식별자 이스케이프 문자 → DDL 인젝션 방지 위해 금지
        raise ValueError(f"{kind}에 백틱(`)을 포함할 수 없습니다: {value!r}")
    if any(unicodedata.category(c) in _FORBIDDEN_CATEGORIES for c in v):
        raise ValueError(
            f"{kind}에 허용되지 않는 문자(제어/포맷/구분자)가 있습니다: {value!r}"
        )
    if len(v) > _MAX_IDENT_LEN:
        raise ValueError(f"{kind}이(가) 너무 깁니다(>{_MAX_IDENT_LEN}): {value!r}")
    return v


# 라벨/관계타입은 '_' 프리픽스를 예약한다. 내부/메타 식별자(:_Entity 기본 라벨,
# :_Project 메타노드, _project/_name 속성)와 사용자 타입 라벨/관계타입이 충돌하면
# 설계 불변식 §4(메타 vs 인스턴스 분리)가 무너진다(예: 사용자 라벨 "_Entity"가
# 프로젝트 삭제 DETACH DELETE의 대상이 됨). 값인 이름/설명엔 이 제약을 두지 않는다.
_RESERVED_IDENT_PREFIX = "_"


def _clean_label_or_type(value: str, kind: str) -> str:
    """라벨/관계타입 전용 정제·검증: 공통 정제 + '_' 프리픽스(내부/메타 예약) 거부."""
    v = _clean_identifier(value, kind)
    if v.startswith(_RESERVED_IDENT_PREFIX):
        raise ValueError(
            f"{kind}은(는) '{_RESERVED_IDENT_PREFIX}'로 시작할 수 없습니다"
            f"(내부/메타 예약): {value!r}"
        )
    return v


# ==================================================================
# v2: 지식그래프 표현 (Entity/Relation/Extraction) — PLAN.md §3
# ==================================================================

_MAX_VALUE_LEN = 500


def _clean_value(value: str, kind: str, maxlen: int = _MAX_VALUE_LEN) -> str:
    """엔티티 이름 등 '값' 정제. 파라미터 바인딩되므로 백틱은 허용하되, 제어/포맷/구분자
    문자는 거부하고 NFC 정규화 + 앞뒤 공백 제거 + 길이 제한을 적용한다."""
    if not isinstance(value, str):
        raise ValueError(f"{kind}은(는) 문자열이어야 합니다: {value!r}")
    v = unicodedata.normalize("NFC", value).strip()
    if not v:
        raise ValueError(f"{kind}은(는) 비어 있을 수 없습니다")
    if any(unicodedata.category(c) in _FORBIDDEN_CATEGORIES for c in v):
        raise ValueError(f"{kind}에 허용되지 않는 문자(제어/포맷/구분자)가 있습니다: {value!r}")
    if len(v) > maxlen:
        raise ValueError(f"{kind}이(가) 너무 깁니다(>{maxlen}): {value!r}")
    return v


class Entity(BaseModel):
    """지식 노드. 예: (녹조:현상), (관심:경보단계)."""

    name: str  # 값(파라미터 바인딩)
    type: str = ""  # 타입 라벨(식별자). 비면 미분류
    description: str = ""

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _clean_value(v, "엔티티 이름(name)")

    @field_validator("type")
    @classmethod
    def _v_type(cls, v: str) -> str:
        # 비어 있으면 '미분류'로 허용. 값이 있으면 라벨 규칙으로 검증.
        if not isinstance(v, str) or not v.strip():
            return ""
        return _clean_label_or_type(v, "엔티티 타입(type)")


class Relation(BaseModel):
    """지식 관계. 예: (녹조)-[원인]->(남조류)."""

    source: str  # 값(엔티티 이름)
    target: str  # 값(엔티티 이름)
    type: str  # 관계타입(식별자) — 필수
    description: str = ""

    @field_validator("source", "target")
    @classmethod
    def _v_endpoints(cls, v: str) -> str:
        return _clean_value(v, "관계 끝점 이름(source/target)")

    @field_validator("type")
    @classmethod
    def _v_type(cls, v: str) -> str:
        return _clean_label_or_type(v, "관계타입(relationship type)")


class Extraction(BaseModel):
    """Claude 추출 결과(미리보기 및 ingest 요청 공용)."""

    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    summary: str = ""
