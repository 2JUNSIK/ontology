"""녹조 관리 / 수질오염 대응 도메인 가이드 (PLAN.md §8).

용도: `claude_extractor.py`(N3)의 추출 프롬프트 **안정 프리픽스**로 `DOMAIN_GUIDE`를
사용한다(prompt caching 대상). 실무 임계값·모델링 가이드가 여기 포함된다.

주의: 이 가이드는 '출발점'이지 정답이 아니다. 실제 지식그래프는 직원의 자연어 입력 +
Claude 추출 + 사용자 편집으로 확정된다.
"""

from __future__ import annotations

# ------------------------------------------------------------------
# 수질 항목(관측 지표)과 단위 — 도메인 가이드 상수
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


def _threshold_line() -> str:
    parts = [f"{k} ≥ {v:,} cells/mL" for k, v in ALGAE_ALERT_THRESHOLDS.items()]
    return " / ".join(parts)


# Claude 추출 프롬프트의 안정 프리픽스로 쓰이는 도메인 모델링 가이드(prompt caching 대상).
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
