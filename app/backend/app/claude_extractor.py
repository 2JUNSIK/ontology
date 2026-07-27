"""Claude 지식 추출 (v2, N3).

자연어 지식 문장 → 엔티티(노드) + 관계 추출. SDK 호출 형태는 `claude-api` 스킬 기준
(모델 `claude-opus-4-8`, `client.messages.parse(output_format=...)` → `parsed_output`).

핵심 설계:
- **구조화 출력**: free-form dict를 피하려 전용 출력 스키마(`_ExtractionOut`)로 받고 내부
  `Extraction`으로 **재검증**한다. 타입 라벨/관계타입은 `_clean_label_or_type` 방어선을
  통과해야 하며(백틱/제어/'_'프리픽스 거부), 실패한 항목은 조용히 드롭한다.
- **prompt caching**: 안정 프리픽스(시스템 지침 + 도메인 가이드)에 cache_control.
- **우아한 열화**: 키 없음/빈 입력/호출 실패 시 빈 `Extraction` → 사용자는 수동 편집으로 계속.
- **비용**: `extract()`는 호출마다 실제 Claude를 부른다(과금).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from .config import settings
from .models import Entity, Extraction, Relation
from .ontology_normalizer import canonicalize_extraction
from .seed_ontology import DOMAIN_GUIDE

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Claude 출력 스키마 (structured output)
# ------------------------------------------------------------------
class _EntityOut(BaseModel):
    name: str
    type: str = ""
    description: str = ""


class _RelationOut(BaseModel):
    source: str
    target: str
    type: str
    description: str = ""


class _ExtractionOut(BaseModel):
    entities: list[_EntityOut] = Field(default_factory=list)
    relations: list[_RelationOut] = Field(default_factory=list)
    summary: str = ""


SYSTEM_INSTRUCTIONS = (
    "당신은 K-water 녹조/수질 도메인의 지식그래프 구축을 돕는 추출기입니다. "
    "사용자가 입력한 자연어 지식 문장에서 엔티티(노드)와 관계를 추출하세요. "
    "각 엔티티에는 간결한 이름(name), 타입 라벨(type; 예: 현상/생물/제도/경보단계/지표/"
    "오염원/대응조치/기관/저수지/측정소), 선택적 설명(description)을 부여합니다. "
    "각 관계에는 source(출발 엔티티 이름), target(도착 엔티티 이름), 간결한 관계타입(type; "
    "예: 원인/단계/기준지표/유입/관할/측정)을 부여합니다. "
    "같은 개념이 다시 나오면 동일한 이름을 재사용해 중복을 피하세요. "
    "아래 도메인 가이드의 [표준 어휘]에 있는 표준 타입/관계타입을 가능하면 우선 사용하고, "
    "약어·표기차(예: 총인=T-P)는 표준명으로 통일하세요. "
    "타입 라벨과 관계타입 이름에는 백틱(`)·제어문자를 넣지 말고 '_'로 시작하지 마세요. "
    "확실히 문장에 근거한 것만 추출하고, 이름은 짧고 표준적인 명사구로 만드세요."
)


def _stable_prefix() -> str:
    """캐시 대상 안정 프리픽스(시간/난수 등 가변 요소 배제)."""
    return SYSTEM_INSTRUCTIONS + "\n\n" + DOMAIN_GUIDE


def _make_client():
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _to_internal(out: _ExtractionOut) -> Extraction:
    """Claude 출력 → 내부 Extraction. 검증 실패 항목은 드롭(식별자 방어선 통과분만)."""
    entities: list[Entity] = []
    for e in out.entities:
        try:
            entities.append(Entity(name=e.name, type=e.type, description=e.description))
        except (ValidationError, ValueError):
            logger.info("추출 엔티티 검증 실패 → 드롭")
    relations: list[Relation] = []
    for r in out.relations:
        try:
            relations.append(
                Relation(source=r.source, target=r.target, type=r.type, description=r.description)
            )
        except (ValidationError, ValueError):
            logger.info("추출 관계 검증 실패 → 드롭")
    # 표준 어휘로 정규화(별칭→표준명, 비표준 타입 관대 통과, 중복 병합). 신뢰는 프롬프트가
    # 아니라 이 후처리에 둔다(설계 불변식 §3 정신).
    return canonicalize_extraction(
        Extraction(entities=entities, relations=relations, summary=out.summary)
    )


def extract(
    text: str,
    existing_entities: list[str] | None = None,
    existing_types: list[str] | None = None,
) -> Extraction:
    """지식 문장에서 엔티티/관계 추출. 키 없음/빈 입력/실패 시 빈 Extraction(우아한 열화).

    existing_entities/types: 기존 그래프의 이름/타입 힌트(일관성·중복 최소화 유도).
    """
    text = (text or "").strip()
    if not settings.anthropic_api_key or not text:
        if not settings.anthropic_api_key:
            logger.info("ANTHROPIC_API_KEY 없음 → 추출 건너뜀")
        return Extraction()

    hint = ""
    if existing_entities:
        hint += "\n\n[이미 그래프에 있는 엔티티(같은 개념이면 이 이름을 재사용)]\n" + ", ".join(
            existing_entities[:200]
        )
    if existing_types:
        hint += "\n\n[이미 쓰인 타입 라벨(가능하면 일관되게 사용)]\n" + ", ".join(
            existing_types[:100]
        )
    user_content = "[입력 지식]\n" + text + hint + "\n\n위 문장에서 엔티티와 관계를 추출하세요."

    try:
        resp = _make_client().messages.parse(
            model=settings.anthropic_model,
            max_tokens=4000,
            system=[
                {
                    "type": "text",
                    "text": _stable_prefix(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
            output_format=_ExtractionOut,
        )
    except Exception as e:  # noqa: BLE001 — API/네트워크 실패는 수동 편집 흐름을 살린다
        logger.warning("Claude 추출 API 호출 실패: %s", type(e).__name__)
        return Extraction()

    out = resp.parsed_output
    if out is None:
        logger.warning("Claude 구조화 출력 없음(refusal 또는 max_tokens 가능)")
        return Extraction()
    return _to_internal(out)
