"""/api 스키마 관련 라우터.

M2: POST /api/suggest — 설문 답변 → draft 스키마(규칙 기반). Claude 보강은 M3에서 채운다.
M4: /api/schema, /api/schema/commit 을 여기에 추가할 예정.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..models import EnrichmentResponse, OntologySchema
from ..survey import build_draft

router = APIRouter(prefix="/api", tags=["schema"])


class SuggestRequest(BaseModel):
    # 명시적 null 도 허용해 빈 설문 제출을 관대하게 처리(프론트가 null 을 보낼 수 있음).
    answers: dict[str, Any] | None = None


class SuggestResponse(BaseModel):
    draft: OntologySchema
    enrichment: EnrichmentResponse  # M2에서는 빈 상태(M3에서 Claude가 채움)
    warnings: list[str]  # draft의 설계상 유의점(끊긴 관계/키 부재 등)


@router.post("/suggest", response_model=SuggestResponse)
def suggest(req: SuggestRequest) -> SuggestResponse:
    """설문 답변으로 draft 스키마를 생성한다(M2: Claude 보강 제외)."""
    draft = build_draft(req.answers or {})
    return SuggestResponse(
        draft=draft,
        enrichment=EnrichmentResponse(),
        warnings=draft.consistency_warnings(),
    )
