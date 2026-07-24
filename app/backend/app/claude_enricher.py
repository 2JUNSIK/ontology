"""Claude 보강 (M3).

draft 스키마 + 설문 자유서술을 Claude에 보내 누락 노드/관계/속성·모델링 경고를
`EnrichmentResponse`로 받는다. SDK 호출 형태는 `claude-api` 스킬로 확정(불변식 §5).

핵심 설계:
- **구조화 출력**: structured output은 free-form dict를 지원하지 않으므로, Claude에는
  명시 필드를 가진 전용 스키마(`_EnrichmentOut`)로 받고 내부 `EnrichmentResponse`로 매핑한다.
  매핑 시 payload를 코어 모델(NodeLabel/RelationshipType/PropertyDef)로 **재검증**해
  _clean_identifier 방어선을 통과시킨다(신뢰 불가 LLM 출력, 불변식 §5).
- **prompt caching**: 안정 프리픽스(system 지침 + 시드 온톨로지 JSON + 도메인 가이드)에
  cache_control 적용. 가변부(자유서술 + draft JSON)는 user 턴 → 캐시 안 됨.
  (Opus 4.8 최소 캐시 프리픽스 4096토큰 미만이면 조용히 캐시 미스 — 오류 아님)
- **우아한 열화**: API 키가 없거나 호출이 실패하면 빈 EnrichmentResponse를 반환해
  /api/suggest가 draft만으로도 항상 동작하게 한다.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from .config import settings
from .models import (
    EnrichmentResponse,
    NodeLabel,
    OntologySchema,
    PropertyDef,
    RelationshipType,
    Suggestion,
)
from .seed_ontology import DOMAIN_GUIDE, SEED_ONTOLOGY

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Claude 출력 스키마 (structured output 안전용 — free-form dict 회피)
# ------------------------------------------------------------------
class _PropOut(BaseModel):
    name: str
    type: Literal["string", "int", "float", "date", "boolean"] = "string"
    required: bool = False
    description: str = ""


class _SuggestionOut(BaseModel):
    kind: Literal["add_node", "add_relationship", "add_property", "warning"]
    target: str
    rationale: str
    # payload 상세 (kind에 따라 필요한 것만 채움)
    node_label: str | None = None
    key_property: str | None = None
    properties: list[_PropOut] = Field(default_factory=list)
    relationship_type: str | None = None
    start_label: str | None = None
    end_label: str | None = None


class _EnrichmentOut(BaseModel):
    summary: str = ""
    suggestions: list[_SuggestionOut] = Field(default_factory=list)


SYSTEM_INSTRUCTIONS = (
    "당신은 K-water 녹조/수질 도메인의 온톨로지 설계를 돕는 전문가입니다. "
    "사용자가 설문으로 만든 draft 스키마와 자유서술을 보고, 누락된 노드/관계/속성과 "
    "모델링 경고를 제안합니다. 특히 (1) 측정값처럼 시각을 잇는 이벤트 노드 분리 필요성, "
    "(2) 노드 간 누락된 관계, (3) UNIQUE 키 속성 부재를 점검하세요. "
    "확실하고 도메인에 맞는 것만 제안하고, 라벨/관계/속성 이름에 백틱이나 제어문자를 넣지 마세요."
)


def _stable_prefix() -> str:
    """캐시 대상 안정 프리픽스. 시간/난수 등 가변 요소를 넣지 않는다(캐시 무효화 방지)."""
    return (
        SYSTEM_INSTRUCTIONS
        + "\n\n[시드 온톨로지(JSON)]\n"
        + SEED_ONTOLOGY.model_dump_json()
        + "\n\n"
        + DOMAIN_GUIDE
    )


def _make_client():
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _payload_for(s: _SuggestionOut) -> dict:
    """제안 kind별 payload를 코어 모델로 **재검증**해 만든다(불변식 §5).

    모든 식별자(라벨/관계타입/속성명/target_label)는 코어 모델을 거쳐 _clean_identifier
    방어선을 통과한다. 필수 필드가 없으면 ValueError를 던져 호출측에서 warning으로 강등.
    """
    if s.kind == "add_node":
        if not s.node_label:
            raise ValueError("add_node 제안에 node_label이 필요합니다")
        node = NodeLabel(
            label=s.node_label,
            properties=[PropertyDef(**p.model_dump()) for p in s.properties],
            key_property=s.key_property,
        )
        return node.model_dump()

    if s.kind == "add_relationship":
        if not (s.relationship_type and s.start_label and s.end_label):
            raise ValueError("add_relationship 제안에 type/start_label/end_label이 필요합니다")
        rel = RelationshipType(
            type=s.relationship_type,
            start_label=s.start_label,
            end_label=s.end_label,
            properties=[PropertyDef(**p.model_dump()) for p in s.properties],
        )
        return rel.model_dump()

    if s.kind == "add_property":
        if not s.properties or not s.node_label:
            raise ValueError("add_property 제안에 node_label과 properties가 필요합니다")
        prop = PropertyDef(**s.properties[0].model_dump())
        # target_label도 반드시 재검증/정제 (H1: 이 경로가 §5 방어선을 우회하면 안 됨)
        target = NodeLabel(label=s.node_label)
        data = prop.model_dump()
        data["target_label"] = target.label
        return data

    return {}  # warning


def _map_to_internal(out: _EnrichmentOut) -> EnrichmentResponse:
    """Claude 출력 → 내부 EnrichmentResponse. 검증 실패 제안은 warning으로 강등."""
    suggestions: list[Suggestion] = []
    for s in out.suggestions:
        try:
            payload = _payload_for(s)
        except (ValidationError, ValueError) as e:
            # 잘못된 식별자/필드 누락 제안은 경고로 강등(스키마/Cypher에 새지 않게)
            suggestions.append(
                Suggestion(
                    kind="warning",
                    target=s.target,
                    rationale=f"제안이 검증을 통과하지 못해 경고로 강등: {str(e)[:200]}",
                    payload={},
                )
            )
            continue
        suggestions.append(
            Suggestion(kind=s.kind, target=s.target, rationale=s.rationale, payload=payload)
        )
    return EnrichmentResponse(suggestions=suggestions, summary=out.summary)


def enrich(draft: OntologySchema, answers: dict, free_text: str = "") -> EnrichmentResponse:
    """draft + 자유서술 → Claude 보강 제안. 실패/키부재 시 빈 응답(우아한 열화)."""
    if not settings.anthropic_api_key:
        logger.info("ANTHROPIC_API_KEY 없음 → Claude 보강 건너뜀")
        return EnrichmentResponse()

    user_content = (
        "[설문 자유서술]\n"
        + (free_text.strip() or "(없음)")
        + "\n\n[현재 draft 스키마(JSON)]\n"
        + draft.model_dump_json()
        + "\n\n위 draft에서 누락되었거나 개선이 필요한 부분을 제안해 주세요."
    )

    # API 호출만 좁게 감싼다. _map_to_internal(매핑) 버그까지 여기서 삼키면 제안이 조용히
    # 사라지므로 매핑은 try 밖에서 수행한다.
    try:
        resp = _make_client().messages.parse(
            model=settings.anthropic_model,
            max_tokens=8000,
            # prompt caching: 안정 프리픽스에 cache_control. 단, Opus 4.8 최소 캐시 프리픽스는
            # 4096토큰이며 현재 프리픽스는 ~1600토큰으로 임계값 미달 → 실제로는 캐시 미적용
            # (오류 아님, cache_creation=0). 배선은 유지하되, 시드/가이드가 커지거나 안정 컨텍스트를
            # 프리픽스로 더 옮기면 자동으로 캐시가 활성화된다.
            system=[
                {
                    "type": "text",
                    "text": _stable_prefix(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
            output_format=_EnrichmentOut,
        )
    except Exception as e:  # noqa: BLE001 — API/네트워크 실패는 draft 흐름을 살린다
        # 예외 본문에 요청 데이터가 섞일 수 있어 타입명만 로깅(자유서술 노출 방지)
        logger.warning("Claude 보강 API 호출 실패: %s", type(e).__name__)
        return EnrichmentResponse()

    out = resp.parsed_output
    if out is None:
        logger.warning("Claude 구조화 출력 없음(refusal 또는 max_tokens 가능)")
        return EnrichmentResponse()
    return _map_to_internal(out)
