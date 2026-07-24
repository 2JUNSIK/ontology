"""/api/survey/* 라우터 (M2)."""

from __future__ import annotations

from fastapi import APIRouter

from ..survey import QUESTIONS, SurveyQuestion

router = APIRouter(prefix="/api/survey", tags=["survey"])


@router.get("/questions", response_model=list[SurveyQuestion])
def get_questions() -> list[SurveyQuestion]:
    """설문 문항 목록."""
    return QUESTIONS
