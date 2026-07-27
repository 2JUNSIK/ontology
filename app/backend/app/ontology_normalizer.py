"""온톨로지 정규화 (N9) — 순수 함수.

Claude 추출 결과(`Extraction`)를 표준 어휘로 정규화한다. `cypher_builder`와 마찬가지로
**부수효과·Neo4j 접근이 없는 순수 함수**이며 단위테스트 대상이다(설계 불변식 §2 정신).

두 가지 일을 한다:
1. **엔티티 정규화**: 별칭·약어를 표준명으로(`CANONICAL_ALIASES`), 비표준 타입을 표준 타입으로
   (`TYPE_ALIASES`) 치환한다. `Relation.source/target`도 같은 맵으로 치환해 관계가 표준 노드에
   붙게 한다(끊긴 엣지·중복 방지). 치환 후 같은 이름/같은 (source,type,target)은 병합한다.
   - **비표준 타입은 드롭하지 않고 관대하게 통과**한다(도메인 확장성).
   - 치환 결과는 `Entity`/`Relation`을 재생성해 정제 방어선(`_clean_value`/`_clean_label_or_type`)을
     다시 통과시킨다(치환값에 위험 문자가 섞여 들어오는 것을 차단).
2. **domain/range 검증**: `RELATION_CONSTRAINTS` 위반을 **경고 문자열로만** 반환한다(관계를
   삭제하지 않는다 — '조용한 소실' 방지, CLAUDE.md 원칙). 엔티티 타입이 미상이면 통과(관대).

정규화는 **멱등**이다: `canonicalize_extraction(canonicalize_extraction(x))`는 한 번 적용과 같다.
"""

from __future__ import annotations

import unicodedata

from pydantic import ValidationError

from .models import Entity, Extraction, Relation
from .seed_ontology import CANONICAL_ALIASES, RELATION_CONSTRAINTS, TYPE_ALIASES

# 사전 키를 NFC로 정규화해 조회한다(코드 리터럴/입력의 유니코드 표현 차이 방어).
_NAME_MAP: dict[str, str] = {
    unicodedata.normalize("NFC", k).strip(): v for k, v in CANONICAL_ALIASES.items()
}
_TYPE_MAP: dict[str, str] = {
    unicodedata.normalize("NFC", k).strip(): v for k, v in TYPE_ALIASES.items()
}


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip()


def canonical_name(name: str) -> str:
    """엔티티 이름을 표준명으로. 별칭이 아니면 정제된 원문 그대로."""
    key = _nfc(name)
    return _NAME_MAP.get(key, key)


def canonical_type(type_label: str) -> str:
    """엔티티 타입을 표준 타입으로. 비표준(사전에 없음)은 관대하게 원문 유지. 빈 값은 ''."""
    key = _nfc(type_label)
    if not key:
        return ""
    return _TYPE_MAP.get(key, key)


def _merge_entity(a: Entity, b: Entity) -> Entity:
    """같은 이름의 두 엔티티 병합. 타입·설명은 비어있지 않은 쪽(먼저 등장 `a`) 우선.

    주의(문서화된 동작): 서로 다른 non-empty 타입이 충돌하면 먼저 등장한 `a.type`만 남고
    `b.type`은 버려진다. `Entity.type`이 단일 문자열이라(SSoT 모델 한계) 한 노드에 여러 타입을
    보존할 수 없기 때문이다 — 결정적으로 '문장 근거가 먼저 나온 타입'을 신뢰한다. 다중 타입
    보존이 필요해지면 모델(§1) 확장이 선행되어야 한다.
    """
    return Entity(
        name=a.name,
        type=a.type or b.type,
        description=a.description or b.description,
    )


def _merge_relation(a: Relation, b: Relation) -> Relation:
    """같은 (source,type,target) 관계 병합. 설명은 비어있지 않은 쪽(먼저 등장) 우선."""
    return Relation(
        source=a.source,
        target=a.target,
        type=a.type,
        description=a.description or b.description,
    )


def canonicalize_extraction(ext: Extraction) -> Extraction:
    """추출 결과를 표준 어휘로 정규화한 **새** Extraction을 반환한다(입력 불변).

    치환 결과가 방어선을 위반하면 해당 항목만 드롭한다(전체 실패 없음).
    """
    # 1) 엔티티: 치환 + 이름 기준 dedup(등장 순서 보존)
    merged: dict[str, Entity] = {}
    order: list[str] = []
    for e in ext.entities:
        try:
            ne = Entity(
                name=canonical_name(e.name),
                type=canonical_type(e.type),
                description=e.description,
            )
        except (ValidationError, ValueError):
            continue
        if ne.name not in merged:
            merged[ne.name] = ne
            order.append(ne.name)
        else:
            merged[ne.name] = _merge_entity(merged[ne.name], ne)
    entities = [merged[k] for k in order]

    # 2) 관계: 끝점 치환 + (source,type,target) dedup(등장 순서 보존)
    rmerged: dict[tuple[str, str, str], Relation] = {}
    rorder: list[tuple[str, str, str]] = []
    for r in ext.relations:
        try:
            nr = Relation(
                source=canonical_name(r.source),
                target=canonical_name(r.target),
                type=r.type,
                description=r.description,
            )
        except (ValidationError, ValueError):
            continue
        key = (nr.source, nr.type, nr.target)
        if key not in rmerged:
            rmerged[key] = nr
            rorder.append(key)
        else:
            rmerged[key] = _merge_relation(rmerged[key], nr)
    relations = [rmerged[k] for k in rorder]

    return Extraction(entities=entities, relations=relations, summary=ext.summary)


def validate_domain_range(ext: Extraction) -> list[str]:
    """관계의 domain/range 위반을 경고 문자열 리스트로 반환(관계는 유지). 순수 함수.

    엔티티 타입은 표준화 후 기준. 제약이 없는 관계타입이거나 끝점 타입이 미상이면 통과한다.
    입력이 이미 canonicalize 되었든 아니든 같은 결과가 나오도록 내부에서 표준화한다.
    """
    type_of: dict[str, str] = {}
    for e in ext.entities:
        type_of[canonical_name(e.name)] = canonical_type(e.type)

    warnings: list[str] = []
    for r in ext.relations:
        constraint = RELATION_CONSTRAINTS.get(r.type)
        if not constraint:
            continue
        allowed_src, allowed_tgt = constraint
        s, t = canonical_name(r.source), canonical_name(r.target)
        st, tt = type_of.get(s, ""), type_of.get(t, "")
        # 라벨도 표준명으로 — 경고 문구가 실제 저장될 노드 이름과 일치하도록(사용자 혼동 방지).
        label = f"{s}-[{r.type}]→{t}"
        if st and st not in allowed_src:
            warnings.append(
                f"'{label}': 출발 '{r.source}'의 타입 '{st}'은(는) "
                f"'{r.type}' 관계의 허용 출발 타입({'/'.join(sorted(allowed_src))})이 아닙니다."
            )
        if tt and tt not in allowed_tgt:
            warnings.append(
                f"'{label}': 도착 '{r.target}'의 타입 '{tt}'은(는) "
                f"'{r.type}' 관계의 허용 도착 타입({'/'.join(sorted(allowed_tgt))})이 아닙니다."
            )
    return warnings
