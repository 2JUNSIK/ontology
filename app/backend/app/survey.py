"""설문 문항 정의 + 답변 → draft 스키마 규칙 (M2).

하이브리드 엔진의 (1)단계: 구조화 설문으로 온톨로지 뼈대를 잡는다.
`build_draft`는 **순수 함수**(부수효과 없음)로 만들어 단위테스트로 검증한다.
Claude 보강(M3)은 이 draft가 놓친 부분(예: 측정값 이벤트 노드 분리)을 제안한다.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from .models import OntologySchema
from .seed_ontology import SEED_ONTOLOGY, WATER_QUALITY_ITEMS

QuestionType = Literal["single", "multi", "text"]


class Option(BaseModel):
    id: str
    label: str


class SurveyQuestion(BaseModel):
    id: str
    text: str
    type: QuestionType
    options: list[Option] = Field(default_factory=list)
    help: str = ""


def _opts(*labels: str) -> list[Option]:
    return [Option(id=x, label=x) for x in labels]


# 설문 문항 (녹조/수질 도메인, PLAN.md §4a). 선택형 + 자유서술 혼합.
QUESTIONS: list[SurveyQuestion] = [
    SurveyQuestion(
        id="assets", type="multi", text="관리 대상 물리 자산은?",
        options=_opts("저수지", "보", "취수장", "정수장"),
        help="MVP 시드는 '저수지'만 매핑합니다. 나머지는 Claude 보강/편집에서 추가하세요.",
    ),
    SurveyQuestion(
        id="has_station", type="single", text="수질을 측정하는 '측정소' 개념이 있나요?",
        options=_opts("예", "아니오"),
    ),
    SurveyQuestion(
        id="water_items", type="multi", text="어떤 수질 항목을 관측하나요?",
        options=_opts(*[name for name, _unit in WATER_QUALITY_ITEMS]),
    ),
    SurveyQuestion(
        id="algae_alert", type="single", text="조류경보제를 운영하나요? (관심/경계/대발생 단계)",
        options=_opts("예", "아니오"),
    ),
    SurveyQuestion(
        id="pollution_sources", type="multi", text="오염원을 추적하나요?",
        options=_opts("점오염원", "비점오염원"),
    ),
    SurveyQuestion(
        id="measures", type="multi", text="어떤 대응조치를 하나요?",
        options=_opts("조류제거선", "살수", "방류량 조절"),
    ),
    SurveyQuestion(
        id="organizations", type="multi", text="관련 기관·조직은?",
        options=_opts("유역환경청", "지자체", "물관리센터"),
    ),
    SurveyQuestion(
        id="free_text", type="text",
        text="위에서 다루지 못한 중요한 개념/관계를 설명해 주세요.",
        help="자유서술. M3에서 Claude가 이 내용을 분석해 누락 노드/관계를 제안합니다.",
    ),
]

_QUESTION_IDS = {q.id for q in QUESTIONS}


# ------------------------------------------------------------------
# 답변 → draft 규칙
# ------------------------------------------------------------------

def _as_list(v: Any) -> list[str]:
    """답변 값을 문자열 리스트로 정규화. 빈 문자열/공백은 제외."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    if isinstance(v, (list, tuple, set)):
        return [str(x).strip() for x in v if str(x).strip()]
    return []


def _as_str(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def selected_labels(answers: Mapping[str, Any]) -> set[str]:
    """설문 답변에서 draft에 포함할 시드 노드 라벨 집합을 도출한다.

    주의: 측정 '값'을 잇는 이벤트 노드(측정값)는 규칙으로 추가하지 않는다 —
    이는 Claude 보강(M3)이 제안하도록 남겨 하이브리드의 가치를 보인다.
    """
    labels: set[str] = set()

    if "저수지" in _as_list(answers.get("assets")):
        labels.add("저수지")
    if _as_str(answers.get("has_station")) == "예":
        labels.add("측정소")
    if _as_list(answers.get("water_items")):
        labels.add("수질항목")
    if _as_str(answers.get("algae_alert")) == "예":
        labels.add("조류경보")
    if any(p in ("점오염원", "비점오염원") for p in _as_list(answers.get("pollution_sources"))):
        labels.add("오염원")
    if _as_list(answers.get("measures")):
        labels.add("대응조치")
    if _as_list(answers.get("organizations")):
        labels.add("기관")

    return labels


def build_draft(answers: Mapping[str, Any]) -> OntologySchema:
    """설문 답변 → draft OntologySchema (순수 함수).

    - 선택된 라벨의 시드 노드만 포함.
    - 양 끝 라벨이 모두 선택된 시드 관계만 포함(끊긴 관계 방지).
    - 시드 객체를 deep copy 해 반환한다. 따라서 반환된 draft를 이후 편집해도
      (M3 Claude 보강 반영 / M4 사용자 편집) 전역 SEED_ONTOLOGY가 오염되지 않는다.
      입력 answers도 변형하지 않는다.
    반환값은 OntologySchema 검증을 통과한 상태다.
    """
    labels = selected_labels(answers)
    nodes = [n.model_copy(deep=True) for n in SEED_ONTOLOGY.nodes if n.label in labels]
    rels = [
        r.model_copy(deep=True)
        for r in SEED_ONTOLOGY.relationships
        if r.start_label in labels and r.end_label in labels
    ]
    return OntologySchema(nodes=nodes, relationships=rels)
