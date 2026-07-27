"""자연어 → Cypher 생성 (v2 읽기 경로, N8).

사용자의 자연어 질문을 프로젝트 지식그래프 탐색용 **읽기 전용 Cypher**로 변환한다.
SDK 호출 형태는 claude_extractor와 동일(`messages.parse(output_format=...)` → `parsed_output`).

핵심 설계:
- **구조화 출력**: `_QueryOut`(cypher/explanation/result_kind)로 받는다(free-form dict 회피).
- **안전은 '생성'이 아니라 '검증·실행'에서 보장한다**: 여기서 만든 Cypher는 라우터가
  `cypher_builder.assert_read_only_cypher`로 정적 검증하고, neo4j_service가 READ access mode
  트랜잭션으로만 실행한다. 프롬프트는 '읽기 전용 + $pid 필터'를 강하게 유도할 뿐, 그 자체가
  신뢰의 근거는 아니다(LLM 출력은 신뢰하지 않는다 — 불변식 §3의 읽기 경로 확장).
- **prompt caching**: 안정 프리픽스(스키마 규칙 + DOMAIN_GUIDE)에 cache_control.
- **우아한 열화**: 키 없음/빈 질문/호출 실패 시 None → 라우터가 빈 결과로 응답.
- **비용**: generate_query()는 호출마다 실제 Claude를 부른다(과금).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from .claude_extractor import _make_client  # SDK 클라이언트 생성 재사용
from .config import settings
from .seed_ontology import DOMAIN_GUIDE

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Claude 출력 스키마 (structured output)
# ------------------------------------------------------------------
class _QueryOut(BaseModel):
    cypher: str = ""  # 읽기 전용 Cypher 한 문(빈 문자열이면 '변환 불가')
    explanation: str = ""  # 이 질의가 무엇을 조회하는지 한국어 한 문장
    result_kind: str = "graph"  # graph | table | none (프론트 표시 힌트, 참고용)


SYSTEM_INSTRUCTIONS = (
    "당신은 K-water 녹조/수질 지식그래프를 탐색하는 Cypher 질의를 생성하는 도우미입니다. "
    "사용자의 자연어 질문을 Neo4j 5 Cypher **읽기 전용** 질의 한 개로 변환하세요.\n\n"
    "[데이터 모델]\n"
    "- 모든 지식 노드: (n:`_Entity` {_project, _name, description}) + 동적 타입 라벨"
    "(예: :현상, :생물, :경보단계). 노드의 이름은 n._name 속성입니다.\n"
    "- 관계: (a:`_Entity`)-[r]->(b:`_Entity`) — 같은 프로젝트, 동적 관계타입 + r.description.\n\n"
    "[반드시 지킬 규칙]\n"
    "1. 읽기 전용만: MATCH / OPTIONAL MATCH / WHERE / WITH / RETURN / ORDER BY / SKIP / "
    "LIMIT / UNWIND / count 등 집계만 사용하세요. CREATE·MERGE·DELETE·SET·REMOVE·DETACH·"
    "DROP·FOREACH·LOAD·CALL·USE 는 절대 쓰지 마세요.\n"
    "2. 프로젝트 격리: 모든 `_Entity` 패턴에 {_project: $pid} 필터를 넣고, 프로젝트 식별자는 "
    "반드시 파라미터 $pid 로만 참조하세요(값을 문자열로 직접 넣지 말 것).\n"
    "3. 노드 이름 매칭은 _name 속성으로 하세요(예: WHERE n._name = '녹조'). 타입은 라벨입니다.\n"
    "4. 관계·경로 탐색이면 노드/관계를 그대로 RETURN 하세요(예: RETURN n, r, m) — 그러면 "
    "그래프로 시각화됩니다. 개수·목록·집계면 스칼라를 RETURN 하세요. result_kind는 전자면 "
    "'graph', 후자면 'table'.\n"
    "5. 결과 폭주를 막도록 적절한 LIMIT(기본 100)을 넣으세요. 문장은 한 개만(세미콜론 금지).\n"
    "6. explanation에는 이 질의가 무엇을 조회하는지 한국어 한 문장으로 적으세요.\n"
    "질문이 그래프 탐색과 무관하거나 안전하게 변환할 수 없으면 cypher를 빈 문자열로, "
    "result_kind를 'none'으로 두세요."
)


def _stable_prefix() -> str:
    """캐시 대상 안정 프리픽스(질문·힌트 등 가변 요소 배제)."""
    return SYSTEM_INSTRUCTIONS + "\n\n" + DOMAIN_GUIDE


def generate_query(
    question: str,
    types: list[str] | None = None,
    rel_types: list[str] | None = None,
    entity_names: list[str] | None = None,
) -> _QueryOut | None:
    """자연어 질문 → 읽기 전용 Cypher(_QueryOut). 키 없음/빈 질문/실패 시 None(우아한 열화).

    types/rel_types/entity_names: 현재 프로젝트 스키마 힌트(정확한 라벨·이름 사용 유도).
    """
    question = (question or "").strip()
    if not settings.anthropic_api_key or not question:
        if not settings.anthropic_api_key:
            logger.info("ANTHROPIC_API_KEY 없음 → 질의 생성 건너뜀")
        return None

    hint = ""
    if types:
        hint += "\n\n[이 프로젝트의 타입 라벨]\n" + ", ".join(types[:100])
    if rel_types:
        hint += "\n\n[이 프로젝트의 관계타입]\n" + ", ".join(rel_types[:100])
    if entity_names:
        hint += "\n\n[이 프로젝트의 엔티티 이름(일부)]\n" + ", ".join(entity_names[:200])
    user_content = (
        "[질문]\n" + question + hint + "\n\n위 질문을 탐색하는 읽기 전용 Cypher를 만드세요."
    )

    try:
        resp = _make_client().messages.parse(
            model=settings.anthropic_model,
            max_tokens=1500,
            system=[
                {
                    "type": "text",
                    "text": _stable_prefix(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
            output_format=_QueryOut,
        )
    except Exception as e:  # noqa: BLE001 — API/네트워크 실패는 탐색 UX를 죽이지 않는다
        logger.warning("Claude 질의 생성 API 호출 실패: %s", type(e).__name__)
        return None

    out = resp.parsed_output
    if out is None:
        logger.warning("Claude 질의 생성 구조화 출력 없음(refusal 또는 max_tokens 가능)")
        return None
    return out
