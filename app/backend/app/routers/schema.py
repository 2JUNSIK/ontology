"""/api 스키마 관련 라우터.

M2: POST /api/suggest — 설문 답변 → draft 스키마(규칙 기반).
M3: /api/suggest 에 Claude 보강(enrichment) 연결.
M4: /api/schema, /api/schema/commit 을 여기에 추가할 예정.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..claude_enricher import enrich
from ..models import EnrichmentResponse, OntologySchema
from ..survey import build_draft

router = APIRouter(prefix="/api", tags=["schema"])


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
