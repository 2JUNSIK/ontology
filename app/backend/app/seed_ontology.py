"""녹조 관리 / 수질오염 대응 도메인 시드 온톨로지 (PLAN.md §8).

용도:
1. `survey.py`(M2)가 설문 선택지를 이 시드의 노드/관계로 매핑해 draft 스키마를 만든다.
2. `claude_enricher.py`(M3)의 프롬프트 **안정 프리픽스**로 `DOMAIN_GUIDE`를 사용한다
   (prompt caching 대상). 실무 임계값·모델링 가이드가 여기 포함된다.

주의: 이 시드는 '출발점'이지 정답이 아니다. 실제 스키마는 설문 + Claude 보강 + 사용자
편집으로 확정된다.
"""

from __future__ import annotations

from .models import NodeLabel, OntologySchema, PropertyDef, RelationshipType

# ------------------------------------------------------------------
# 수질 항목(관측 지표)과 단위 — 설문/시드/가이드 공용 상수
# ------------------------------------------------------------------
WATER_QUALITY_ITEMS: list[tuple[str, str]] = [
    ("클로로필-a", "μg/L"),
    ("남조류세포수", "cells/mL"),
    ("T-P", "mg/L"),   # 총인
    ("T-N", "mg/L"),   # 총질소
    ("DO", "mg/L"),    # 용존산소
    ("수온", "℃"),
    ("pH", "-"),
    ("COD", "mg/L"),
    ("BOD", "mg/L"),
]

# 조류경보제 단계(남조류세포수 기준, cells/mL)
ALGAE_ALERT_THRESHOLDS: dict[str, int] = {
    "관심": 1_000,
    "경계": 10_000,
    "대발생": 1_000_000,
}


def _p(name: str, type_: str = "string", required: bool = False, description: str = "") -> PropertyDef:
    return PropertyDef(name=name, type=type_, required=required, description=description)


# ------------------------------------------------------------------
# 노드 라벨
# ------------------------------------------------------------------
_NODES: list[NodeLabel] = [
    NodeLabel(
        label="저수지",
        properties=[
            _p("명칭", "string", required=True),
            _p("위치", "string"),
            _p("저수량", "float", description="단위: 백만 m³"),
        ],
        key_property="명칭",
        description="관리 대상 저수지/댐. (자연키가 명확치 않아 우선 명칭을 키로 둠 — 코드 도입 권장)",
    ),
    NodeLabel(
        label="측정소",
        properties=[
            _p("측정소코드", "string", required=True),
            _p("명칭", "string"),
            _p("위도", "float"),
            _p("경도", "float"),
        ],
        key_property="측정소코드",
        description="수질을 측정하는 지점.",
    ),
    NodeLabel(
        label="수질항목",
        properties=[
            _p("항목명", "string", required=True),
            _p("단위", "string"),
        ],
        key_property="항목명",
        description="관측 지표. 예: 클로로필-a(μg/L), 남조류세포수(cells/mL), T-P, T-N, DO, 수온.",
    ),
    NodeLabel(
        label="측정값",
        properties=[
            _p("값", "float", required=True),
            _p("측정시각", "date", required=True),
        ],
        key_property=None,
        description="측정소×항목×시각을 잇는 이벤트 노드. 정체성은 관계로 표현(별도 자연키 없음).",
    ),
    NodeLabel(
        label="조류경보",
        properties=[
            _p("단계", "string", required=True, description="관심/경계/대발생"),
            _p("발령일", "date"),
            _p("해제일", "date"),
        ],
        key_property=None,
        description="조류경보제 발령 이벤트.",
    ),
    NodeLabel(
        label="오염원",
        properties=[
            _p("명칭", "string", required=True),
            _p("유형", "string", description="점오염원/비점오염원"),
        ],
        key_property="명칭",
        description="수질오염 유발원.",
    ),
    NodeLabel(
        label="대응조치",
        properties=[
            _p("조치유형", "string", required=True, description="조류제거선/살수/방류량 조절 등"),
            _p("시행일", "date"),
        ],
        key_property=None,
        description="녹조/오염 대응 조치 이벤트.",
    ),
    NodeLabel(
        label="기관",
        properties=[
            _p("기관명", "string", required=True),
            _p("유형", "string", description="유역환경청/지자체/물관리센터 등"),
        ],
        key_property="기관명",
        description="관련 기관·조직.",
    ),
]

# ------------------------------------------------------------------
# 관계 타입
# ------------------------------------------------------------------
_RELATIONSHIPS: list[RelationshipType] = [
    RelationshipType(type="위치", start_label="측정소", end_label="저수지",
                     description="측정소가 어느 저수지에 속하는지."),
    RelationshipType(type="측정", start_label="측정소", end_label="수질항목",
                     description="측정소가 어떤 항목을 측정하는지."),
    RelationshipType(type="항목", start_label="측정값", end_label="수질항목",
                     description="측정값이 어떤 항목인지."),
    RelationshipType(type="관측지점", start_label="측정값", end_label="측정소",
                     description="측정값이 어느 측정소에서 관측됐는지."),
    RelationshipType(type="발령", start_label="저수지", end_label="조류경보",
                     description="저수지에 조류경보가 발령됨."),
    RelationshipType(type="근거지표", start_label="조류경보", end_label="수질항목",
                     description="경보 발령 근거가 된 지표(예: 남조류세포수)."),
    RelationshipType(type="유입", start_label="오염원", end_label="저수지",
                     description="오염원이 저수지로 유입됨."),
    RelationshipType(type="대상", start_label="대응조치", end_label="저수지",
                     description="대응조치의 대상 저수지."),
    RelationshipType(type="관할", start_label="기관", end_label="저수지",
                     description="기관이 저수지를 관할함."),
    RelationshipType(type="시행", start_label="기관", end_label="대응조치",
                     description="기관이 대응조치를 시행함."),
]

# 파이프라인 전 구간이 참조하는 시드 스키마(생성 시점에 models.py 검증을 통과함).
SEED_ONTOLOGY: OntologySchema = OntologySchema(nodes=_NODES, relationships=_RELATIONSHIPS)


def _threshold_line() -> str:
    parts = [f"{k} ≥ {v:,} cells/mL" for k, v in ALGAE_ALERT_THRESHOLDS.items()]
    return " / ".join(parts)


# Claude 보강 프롬프트의 안정 프리픽스로 쓰이는 도메인 모델링 가이드(prompt caching 대상).
DOMAIN_GUIDE: str = f"""\
[도메인: K-water 녹조 관리 / 수질오염 대응 온톨로지 모델링 가이드]

핵심 개념(노드): 저수지, 측정소, 수질항목, 측정값, 조류경보, 오염원, 대응조치, 기관.

모델링 원칙:
- 측정값은 (측정소 × 수질항목 × 측정시각)을 잇는 **별도 이벤트 노드**로 분리한다.
  값을 측정소나 항목의 속성으로 넣지 말 것(시계열/다대다 표현 불가해짐).
- 조류경보는 발령 이벤트 노드로 두고, 근거지표(예: 남조류세포수)와 연결한다.
- 각 개념의 식별 속성(key)을 정하고 UNIQUE 제약을 부여할 것(예: 측정소=측정소코드).

조류경보제 단계(남조류세포수 기준): {_threshold_line()}.

수질 항목·단위 예시: {", ".join(f"{n}({u})" for n, u in WATER_QUALITY_ITEMS)}.
"""
