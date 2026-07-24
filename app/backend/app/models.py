"""공통 중간표현 (Single Source of Truth).

설문(survey) · Claude 보강(claude_enricher) · Neo4j 반영(cypher_builder) · 프론트(types.ts)가
모두 공유하는 온톨로지 스키마 표현. 새 필드는 반드시 이 모델에서 시작해 양쪽으로 전파한다.
(설계 불변식 §1 — CLAUDE.md 참조)

검증 방침:
- 여기서는 **구조적 정합성**만 강제한다(식별자 비어있음/백틱/중복, key_property 존재 등).
- 라벨/관계타입의 최종 화이트리스트 검증과 백틱 이스케이프는 cypher_builder(불변식 §3)에서
  한 번 더 수행한다. 여기서 백틱을 금지하는 이유는 DDL 인젝션의 1차 방어선이기 때문이다.
- 라벨/속성명에 한글을 허용한다(예: "측정소", "측정소코드"). Neo4j에서 백틱으로 감싸면
  유효한 식별자다. 따라서 ASCII로 제한하지 않는다.
"""

from __future__ import annotations

import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# PLAN.md §3 에 정의된 속성 타입 집합.
PropertyType = Literal["string", "int", "float", "date", "boolean"]

_MAX_IDENT_LEN = 100

# 식별자에서 거부하는 유니코드 일반 카테고리:
#   Cc 제어, Cf 포맷(zero-width·RTL override 등), Cs 서로게이트,
#   Co 사용자영역, Cn 미할당, Zl 줄구분, Zp 문단구분
# → 백틱으로 감싸도 생성되는 Cypher DDL/스크립트/로그를 깨거나 인젝션 표면을 만든다.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
_BACKTICKS = ("`", "｀")  # ASCII 백틱 + 전각 백틱(｀) 모두 금지


def _clean_identifier(value: str, kind: str) -> str:
    """라벨/관계타입/속성명/키 공통 정제·검증. 정제(NFC + trim)된 문자열을 돌려준다.

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


class PropertyDef(BaseModel):
    """노드/관계의 속성 정의."""

    name: str
    type: PropertyType = "string"
    required: bool = False
    description: str = ""

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _clean_identifier(v, "속성명(property name)")


def _validate_unique_property_names(properties: list[PropertyDef]) -> None:
    seen: set[str] = set()
    for p in properties:
        if p.name in seen:
            raise ValueError(f"속성명이 중복되었습니다: {p.name!r}")
        seen.add(p.name)


class NodeLabel(BaseModel):
    """노드 라벨 정의. 예: (:측정소 {측정소코드, 명칭, 위도, 경도})."""

    label: str
    properties: list[PropertyDef] = Field(default_factory=list)
    key_property: str | None = None  # UNIQUE 제약 대상
    description: str = ""

    @field_validator("label")
    @classmethod
    def _v_label(cls, v: str) -> str:
        return _clean_identifier(v, "라벨(label)")

    @field_validator("key_property")
    @classmethod
    def _v_key(cls, v: str | None) -> str | None:
        # key_property도 속성명과 동일하게 정제해야 (a) 공백 차이 오탐과
        # (b) 정제 안 된 문자가 제약 DDL로 새는 것을 막는다.
        if v is None:
            return None
        return _clean_identifier(v, "key_property")

    @model_validator(mode="after")
    def _v_consistency(self) -> "NodeLabel":
        _validate_unique_property_names(self.properties)
        if self.key_property is not None:
            names = {p.name for p in self.properties}
            if self.key_property not in names:
                raise ValueError(
                    f"라벨 '{self.label}'의 key_property '{self.key_property}'가 "
                    f"속성 목록에 없습니다: {sorted(names)}"
                )
        return self


class RelationshipType(BaseModel):
    """관계 타입 정의. 예: (:측정소)-[:측정]->(:수질항목)."""

    type: str
    start_label: str
    end_label: str
    properties: list[PropertyDef] = Field(default_factory=list)
    description: str = ""

    @field_validator("type")
    @classmethod
    def _v_type(cls, v: str) -> str:
        return _clean_identifier(v, "관계타입(relationship type)")

    @field_validator("start_label", "end_label")
    @classmethod
    def _v_labels(cls, v: str) -> str:
        return _clean_identifier(v, "관계의 라벨(start/end label)")

    @model_validator(mode="after")
    def _v_props(self) -> "RelationshipType":
        _validate_unique_property_names(self.properties)
        return self

    @property
    def signature(self) -> tuple[str, str, str]:
        """(type, start_label, end_label) — 중복 판별용 서명."""
        return (self.type, self.start_label, self.end_label)


class OntologySchema(BaseModel):
    """온톨로지 스키마 전체(노드 + 관계). 파이프라인 전 구간의 단일 표현."""

    nodes: list[NodeLabel] = Field(default_factory=list)
    relationships: list[RelationshipType] = Field(default_factory=list)

    @model_validator(mode="after")
    def _v_no_duplicates(self) -> "OntologySchema":
        # 라벨 중복 금지
        seen_labels: set[str] = set()
        for n in self.nodes:
            if n.label in seen_labels:
                raise ValueError(f"노드 라벨이 중복되었습니다: {n.label!r}")
            seen_labels.add(n.label)
        # (type, start, end) 동일 관계 중복 금지
        seen_rels: set[tuple[str, str, str]] = set()
        for r in self.relationships:
            if r.signature in seen_rels:
                raise ValueError(f"동일한 관계가 중복되었습니다: {r.signature}")
            seen_rels.add(r.signature)
        return self

    @property
    def labels(self) -> set[str]:
        return {n.label for n in self.nodes}

    def node(self, label: str) -> NodeLabel | None:
        return next((n for n in self.nodes if n.label == label), None)

    def consistency_warnings(self) -> list[str]:
        """오류(raise)로 다루기엔 이른, 설계상 유의점을 경고로 반환한다.

        draft를 점진적으로 만드는 과정에서 관계가 아직 없는 라벨을 참조할 수 있으므로
        이는 예외 대신 경고로 처리한다(Claude 보강/프론트가 사용자에게 표시).
        """
        warnings: list[str] = []
        labels = self.labels
        for r in self.relationships:
            for role, lbl in (("start", r.start_label), ("end", r.end_label)):
                if lbl not in labels:
                    warnings.append(
                        f"관계 '{r.type}'의 {role} 라벨 '{lbl}'에 대응하는 노드 정의가 없습니다."
                    )
        for n in self.nodes:
            if n.key_property is None:
                warnings.append(
                    f"노드 '{n.label}'에 key_property가 없어 UNIQUE 제약을 만들 수 없습니다."
                )
        return warnings


# ------------------------------------------------------------------
# Claude 보강 제안 (구조화 출력용) — PLAN.md §3
# ------------------------------------------------------------------

SuggestionKind = Literal["add_node", "add_relationship", "add_property", "warning"]


class Suggestion(BaseModel):
    """Claude가 내놓는 개별 보강 제안.

    보안 주의: `target`/`payload`는 신뢰할 수 없는 LLM 출력이다. 스키마에 반영할 때는
    반드시 payload를 NodeLabel/RelationshipType/PropertyDef로 **재검증**해 통과시킨 뒤
    사용할 것(그래야 _clean_identifier 방어선을 거친다). payload/target을 Cypher에
    직접 끼워넣지 말 것 (설계 불변식 §3).
    """

    kind: SuggestionKind
    target: str  # 제안 대상(라벨/관계 등 사람이 읽는 식별자; 신뢰 불가)
    rationale: str  # 근거(사용자에게 표시)
    payload: dict = Field(default_factory=dict)  # 사용 전 반드시 코어 모델로 재검증


class EnrichmentResponse(BaseModel):
    """Claude 보강 응답 전체."""

    suggestions: list[Suggestion] = Field(default_factory=list)
    summary: str = ""
