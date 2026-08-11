"""표준 시드 온톨로지 (N15) — 녹조·수질 도메인 스타터팩 (순수 함수).

빈 프로젝트에 곧바로 불러올 수 있는 **큐레이션된 기준 지식그래프**를 `Extraction`으로 만든다.
`cypher_builder`·`ontology_normalizer`와 마찬가지로 **부수효과·Neo4j 접근이 없는 순수 함수**이며
단위테스트 대상이다(설계 불변식 §2 정신). 실행(병합)은 `neo4j_service.ingest`가 담당한다.

설계 원칙:
- **표준 어휘만 사용**한다(seed_ontology.STANDARD_ENTITY_TYPES / STANDARD_RELATION_TYPES) →
  정규화·domain/range 검증을 **무경고**로 통과한다(테스트로 못 박음).
- **임계값은 경보단계 노드의 정량 속성(N10)** 으로 넣는다. 지표 노드(남조류세포수) 하나가 3개
  임계값을 가질 수 없으므로, 관심/경계/대발생 각 노드에 발령 기준값을 얹는다(모델링 결정).
  값은 `ALGAE_ALERT_THRESHOLDS` 상수를 재사용해 DOMAIN_GUIDE와 어긋나지 않게 한다.
- **경량 provenance**: 규제 임계값 노드의 description에 출처·"확인 필요" 문구를 남긴다(정식
  provenance 필드는 후속 마일스톤). 틀린 권위 콘텐츠는 없는 것보다 위험하므로, 발령 세부요건·
  최신 기준·시행일은 단정하지 않고 '확인 필요'로 표기한다.
- MERGE 병합이라 **재불러오기·사용자 입력과의 겹침 모두 멱등**하다((_project,_name) 정체성).
"""

from __future__ import annotations

from .models import Entity, Extraction, Relation
from .seed_ontology import ALGAE_ALERT_THRESHOLDS

# 조류경보 단계 임계값의 근거(경량 provenance). 최신 기준·발령 세부요건은 운영지침 확인 필요.
_ALERT_SOURCE = "출처: 환경부 물환경보전법·국립환경과학원 조류경보제 운영(최신 기준·발령 세부요건·시행일 확인 필요)"


def _alert_stage_entities() -> list[Entity]:
    """관심/경계/대발생 경보단계 — 발령 임계값(남조류세포수)을 정량 속성으로 얹는다."""
    stages: list[Entity] = []
    for name, threshold in ALGAE_ALERT_THRESHOLDS.items():
        stages.append(
            Entity(
                name=name,
                type="경보단계",
                description=(
                    f"조류경보 '{name}' 단계 발령기준: 유해남조류세포수 {threshold:,} cells/mL 이상"
                    f"(2회 연속 채수 시 발령). {_ALERT_SOURCE}."
                ),
                value=float(threshold),
                unit="cells/mL",
                comparator=">=",
            )
        )
    return stages


def build_seed_extraction() -> Extraction:
    """녹조·수질 표준 기준 지식그래프를 담은 Extraction을 반환한다(결정적·순수).

    담는 블록: ① 조류경보제 체계 ② 수질·수문 항목 ③ 상수원·측정소·기관 ④ 오염원 ⑤ 현상·생물·대응조치.
    모든 타입/관계는 표준 어휘이며 domain/range 제약을 만족한다(무경고).
    """
    entities: list[Entity] = []
    relations: list[Relation] = []

    # ── ① 조류경보제 체계 ─────────────────────────────────────────────
    entities.append(
        Entity(
            name="조류경보제",
            type="제도",
            description=(
                "상수원 유해남조류세포수를 기준으로 관심·경계·대발생 3단계를 발령·운영하는 제도. "
                "2024년 개정으로 경계 단계부터 조류독소(마이크로시스틴 등)를 병행 측정한다. "
                f"{_ALERT_SOURCE}."
            ),
        )
    )
    entities.extend(_alert_stage_entities())
    for stage in ("관심", "경계", "대발생"):
        relations.append(Relation(source="조류경보제", target=stage, type="단계"))
        relations.append(
            Relation(
                source=stage,
                target="남조류세포수",
                type="기준지표",
                description="발령 근거 지표(유해남조류세포수).",
            )
        )
    # 2024 개정: 경계 단계 이상에서 조류독소(마이크로시스틴)를 병행 측정·판정한다.
    for stage in ("경계", "대발생"):
        relations.append(
            Relation(
                source=stage,
                target="마이크로시스틴",
                type="기준지표",
                description="2024년 개정 상수원 조류독소 기준(병행 측정).",
            )
        )

    # ── ② 수질·수문 항목 (단위는 description에 — value가 없으면 unit은 coherence로 드롭됨) ──
    water_items: list[tuple[str, str, str]] = [
        ("남조류세포수", "수질항목", "유해남조류 세포수 농도(cells/mL). 조류경보제 발령 근거 지표."),
        (
            "마이크로시스틴",
            "수질항목",
            "남조류(주로 Microcystis)가 생성하는 대표 독소(microcystin). 2024년 개정 상수원 조류독소 "
            "기준(경계 이상 병행 측정, 총 마이크로시스틴 10 μg/L). 최신 기준·시행일 확인 필요.",
        ),
        ("클로로필-a", "수질항목", "식물플랑크톤 현존량 지표(μg/L)."),
        ("T-P", "수질항목", "총인(mg/L). 부영양화·조류 증식의 주요 제한영양염."),
        ("T-N", "수질항목", "총질소(mg/L). 영양염."),
        ("DO", "수질항목", "용존산소(mg/L)."),
        ("pH", "수질항목", "수소이온농도. 조류 광합성으로 상승하기도 한다."),
        ("COD", "수질항목", "화학적산소요구량(mg/L)."),
        ("BOD", "수질항목", "생물화학적산소요구량(mg/L)."),
        ("수온", "수문항목", "수온(℃). 상승 시 남조류 증식에 유리."),
    ]
    for name, etype, desc in water_items:
        # 남조류세포수는 위 관계에서 이미 참조되지만, 엔티티 정의(타입·설명)를 여기서 확정한다.
        entities.append(Entity(name=name, type=etype, description=desc))

    # ── ③ 상수원·측정소·기관 ─────────────────────────────────────────
    entities.extend(
        [
            Entity(name="대청호", type="저수지", description="금강 수계 대청댐 담수호(예시 상수원). 조류경보제 운영 대상."),
            Entity(name="보령댐", type="댐", description="보령댐(예시). 한국수자원공사 관리 댐."),
            Entity(
                name="팔당호",
                type="저수지",
                description="한강 수계 수도권 광역상수원(예시). K-water가 광역상수도·취수시설을 운영.",
            ),
            Entity(
                name="회남 측정소",
                type="측정소",
                description="대청호 조류경보제 측정지점(예시). 남조류세포수·클로로필-a 등 측정.",
            ),
            Entity(
                name="한국수자원공사",
                type="기관",
                description="K-water. 상수원·댐 관리 및 녹조·수질 대응 수행 기관.",
            ),
        ]
    )
    relations.extend(
        [
            Relation(source="회남 측정소", target="남조류세포수", type="측정"),
            Relation(source="회남 측정소", target="클로로필-a", type="측정"),
            Relation(source="회남 측정소", target="대청호", type="위치"),
            Relation(source="한국수자원공사", target="대청호", type="관할"),
            Relation(source="한국수자원공사", target="보령댐", type="관할"),
            Relation(source="한국수자원공사", target="팔당호", type="관할"),
            Relation(source="한국수자원공사", target="회남 측정소", type="관할"),
        ]
    )

    # ── ④ 오염원 ─────────────────────────────────────────────────────
    entities.extend(
        [
            Entity(name="점오염원", type="오염원", description="하수처리장 방류구 등 배출지점이 특정되는 오염원."),
            Entity(name="비점오염원", type="오염원", description="강우 유출 등 배출지점이 특정되지 않는 오염원(농경지·도시 노면 등)."),
            Entity(name="생활하수", type="오염원", description="생활계 하수. 질소·인 등 영양염 공급원."),
            Entity(name="축산", type="오염원", description="축산계 오염원(분뇨 등). 고농도 영양염."),
            Entity(name="농업", type="오염원", description="농업계 비점오염(비료·토양 유출)."),
        ]
    )
    relations.extend(
        [
            Relation(source="점오염원", target="생활하수", type="포함"),
            Relation(source="비점오염원", target="축산", type="포함"),
            Relation(source="비점오염원", target="농업", type="포함"),
            Relation(source="생활하수", target="대청호", type="유입"),
            Relation(source="축산", target="대청호", type="유입"),
            Relation(source="농업", target="대청호", type="유입"),
        ]
    )

    # ── ⑤ 현상·생물·대응조치 ─────────────────────────────────────────
    entities.extend(
        [
            Entity(name="녹조", type="현상", description="남조류가 과도하게 증식해 물이 녹색으로 변하는 현상."),
            Entity(
                name="남조류",
                type="생물",
                description="녹조를 일으키는 남조류(시아노박테리아). 대표 속: Microcystis, Anabaena(Dolichospermum), Aphanizomenon, Oscillatoria 등.",
            ),
            Entity(name="취수구 심도조정", type="대응조치", description="취수 심도를 조류 밀집층보다 깊게 조정해 유입 조류 저감(선택취수)."),
            Entity(name="분말활성탄", type="대응조치", description="정수공정에 분말활성탄(PAC) 주입으로 냄새물질·조류 저감."),
            Entity(name="조류제거선", type="대응조치", description="수면 조류를 물리적으로 수거·제거하는 선박."),
            Entity(name="수면포기장치", type="대응조치", description="수면 포기·순환으로 성층 완화 및 조류 집적 저감."),
            Entity(name="조류차단막", type="대응조치", description="취수구 전면 등에 설치해 조류 유입을 물리적으로 차단."),
        ]
    )
    relations.append(
        Relation(source="녹조", target="남조류", type="원인", description="남조류의 과도한 증식이 녹조의 원인.")
    )
    for measure in ("취수구 심도조정", "분말활성탄", "조류제거선", "수면포기장치", "조류차단막"):
        relations.append(Relation(source=measure, target="녹조", type="대응"))

    return Extraction(
        entities=entities,
        relations=relations,
        summary="녹조·수질 표준 시드 온톨로지: 조류경보제 체계, 수질·수문 항목, 상수원·측정소·기관, 오염원, 현상·생물·대응조치.",
    )
