"""/api 스키마 관련 라우터.

M2: POST /api/suggest — 설문 답변 → draft 스키마(규칙 기반).
M3: /api/suggest 에 Claude 보강(enrichment) 연결.
M4: GET/PUT /api/schema(인메모리 세션 스키마) + POST /api/schema/commit(Neo4j 반영).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..claude_enricher import enrich
from ..models import EnrichmentResponse, OntologySchema
from ..neo4j_service import Neo4jUnavailable, commit_schema
from ..survey import build_draft

router = APIRouter(prefix="/api", tags=["schema"])

# 인메모리 세션 스키마(단일 사용자 MVP, PLAN.md §5). 프로세스 재시작 시 초기화된다.
# 다중 사용자/영속화는 MVP 이후 확장 항목.
_current_schema = OntologySchema()


class SuggestRequest(BaseModel):
    # 명시적 null 도 허용해 빈 설문 제출을 관대하게 처리(프론트가 null 을 보낼 수 있음).
    answers: dict[str, Any] | None = None


class SuggestResponse(BaseModel):
    draft: OntologySchema
    enrichment: EnrichmentResponse  # Claude 보강 제안(키 없거나 실패 시 빈 상태)
    warnings: list[str]  # draft의 설계상 유의점(끊긴 관계/키 부재 등)


def _free_text(answers: dict[str, Any] | None) -> str:
    if isinstance(answers, dict):
        ft = answers.get("free_text")
        if isinstance(ft, str):
            return ft
    return ""


@router.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest) -> SuggestResponse:
    """설문 답변으로 draft 스키마를 만들고 Claude 보강 제안을 덧붙인다."""
    answers = req.answers or {}
    draft = build_draft(answers)
    enrichment = enrich(draft, answers, _free_text(req.answers))
    return SuggestResponse(
        draft=draft,
        enrichment=enrichment,
        warnings=draft.consistency_warnings(),
    )


# ------------------------------------------------------------------
# M4: 세션 스키마 저장/조회 + Neo4j 반영
# ------------------------------------------------------------------


class CommitResponse(BaseModel):
    applied_cypher: list[str]
    stats: dict[str, Any]


@router.get("/schema", response_model=OntologySchema)
def get_schema() -> OntologySchema:
    """현재 세션에 저장된 스키마를 반환한다(사용자 편집의 기준 상태)."""
    return _current_schema


@router.put("/schema", response_model=OntologySchema)
def put_schema(schema: OntologySchema) -> OntologySchema:
    """사용자 편집 결과를 세션 스키마로 저장한다(OntologySchema 검증 통과분만)."""
    global _current_schema
    _current_schema = schema
    return _current_schema


@router.post("/schema/commit", response_model=CommitResponse)
def commit(schema: OntologySchema) -> CommitResponse:
    """확정 스키마를 Neo4j에 반영하고, 실행한 Cypher와 통계를 돌려준다.

    Neo4j 연결 불가 시 503으로 응답(백엔드는 계속 동작). 성공 시 세션 스키마도 갱신한다.
    """
    global _current_schema
    try:
        result = commit_schema(schema)
    except Neo4jUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Neo4j 연결 불가: {e}") from e
    _current_schema = schema
    return CommitResponse(**result)
