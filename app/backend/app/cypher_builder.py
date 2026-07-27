"""지식그래프 ingest: Extraction → Cypher 변환 (v2, PLAN.md §6).

설계 불변식(CLAUDE.md / PLAN.md §6):
- **§2 순수 함수**: `Extraction` → Cypher 문(+파라미터). 부수효과·Neo4j 접근 없음.
  실제 실행은 `neo4j_service`가 담당(관심사 분리). 그래서 단위테스트로 생성물을 검증 가능.
- **§3 인젝션 방지**: 타입 라벨/관계타입 같은 **DDL 식별자**는 화이트리스트(`_clean_identifier`)
  재검증 + 백틱 이스케이프. 값·문자열(엔티티 이름·설명·project_id)은 전부 **파라미터
  바인딩(`$param`)**. 사용자/LLM 문자열을 DDL/패턴에 직접 끼워넣지 않는다.
- **§4 메타 vs 인스턴스 분리**: 프로젝트 메타는 `(:_Project)`, 지식 노드는 공통 기본 라벨
  `(:_Entity {_project,_name})` + 동적 타입 라벨. 정체성 = (_project,_name) 복합 UNIQUE.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from .models import Extraction, _clean_identifier

# v2 지식그래프: 모든 지식 노드의 공통 기본 라벨. 정체성은 (_project,_name)로 잡고,
# 도메인 타입은 이 위에 라벨로 얹는다(다중 라벨). 예: (:_Entity:현상 {_project,_name}).
ENTITY_BASE_LABEL = "_Entity"


@dataclass(frozen=True)
class CypherStatement:
    """실행 단위. neo4j_service가 문/파라미터로 실행하고 kind로 통계를 집계한다."""

    cypher: str
    params: dict = field(default_factory=dict)
    kind: str = ""  # constraint | entity_merge | entity_type | relation


def escape_identifier(ident: str, kind: str = "식별자") -> str:
    """식별자를 재검증(1차 방어선 재확인) 후 백틱 이스케이프(2차 방어선, 불변식 §3).

    `_clean_identifier`가 백틱/제어문자/빈 문자열을 이미 거부하므로 아래 백틱 이중화는
    방어적 중복이다(정상 입력에선 효과 없음). 그래도 유지해 DDL 인젝션 불변식을 국소적으로
    보장한다 — cypher_builder만 봐도 안전함이 명확하도록.
    """
    clean = _clean_identifier(ident, kind)
    return "`" + clean.replace("`", "``") + "`"


# ==================================================================
# v2: 지식그래프 ingest (프로젝트별 엔티티/관계 병합) — PLAN.md §6
# ==================================================================


def build_entity_constraint() -> CypherStatement:
    """엔티티 정체성 제약: (_project,_name) 복합 UNIQUE. 전역 1회(IF NOT EXISTS)."""
    lbl = escape_identifier(ENTITY_BASE_LABEL, "엔티티 기본 라벨")
    cypher = (
        "CREATE CONSTRAINT IF NOT EXISTS "
        f"FOR (n:{lbl}) REQUIRE (n._project, n._name) IS UNIQUE"
    )
    return CypherStatement(cypher=cypher, kind="constraint")


def _entity_set(extraction: Extraction) -> "OrderedDict[str, str]":
    """ingest 대상 엔티티 집합: {이름 -> 설명}. 관계 끝점 중 엔티티 목록에 없는 이름은
    미분류 stub로 보강해 끊긴 관계(=그래프에서 조용히 사라지는 엣지)를 막는다.
    입력 순서를 보존(OrderedDict)해 결정적 출력을 만든다.
    """
    names: "OrderedDict[str, str]" = OrderedDict()
    for e in extraction.entities:
        # 같은 이름이 여러 번이면, 설명이 있는 쪽을 우선 보존.
        if e.name not in names or (not names[e.name] and e.description):
            names[e.name] = e.description
    for r in extraction.relations:
        for nm in (r.source, r.target):
            names.setdefault(nm, "")
    return names


def _entity_types(extraction: Extraction) -> "OrderedDict[str, list[str]]":
    """타입 라벨 -> 그 타입을 가진 엔티티 이름 목록(결정적 순서)."""
    by_type: "OrderedDict[str, list[str]]" = OrderedDict()
    for e in extraction.entities:
        if e.type:
            by_type.setdefault(e.type, [])
            if e.name not in by_type[e.type]:
                by_type[e.type].append(e.name)
    return by_type


def build_ingest_statements(project_id: str, extraction: Extraction) -> list[CypherStatement]:
    """프로젝트 지식그래프에 추출 결과를 병합하는 Cypher 문들(순수 함수, 모두 데이터 연산).

    실행 순서: 엔티티 MERGE → 타입 라벨 부여 → 관계 MERGE. 값(이름/설명/project_id)은 전부
    파라미터 바인딩, 타입 라벨/관계타입만 escape_identifier로 삽입(타입별 그룹핑 — UNWIND로
    라벨을 파라미터화할 수 없기 때문). neo4j_service가 이들을 **하나의 쓰기 트랜잭션**으로
    실행해 원자적으로 반영한다.
    """
    base = escape_identifier(ENTITY_BASE_LABEL, "엔티티 기본 라벨")
    stmts: list[CypherStatement] = []

    # 1) 엔티티 MERGE (이름=정체성, 설명은 비어있지 않을 때만 갱신)
    entities = _entity_set(extraction)
    if entities:
        rows = [{"name": nm, "description": desc} for nm, desc in entities.items()]
        cypher = (
            "UNWIND $rows AS row "
            f"MERGE (n:{base} {{_project: $pid, _name: row.name}}) "
            "SET n.description = CASE WHEN row.description <> '' "
            "THEN row.description ELSE coalesce(n.description, '') END"
        )
        stmts.append(
            CypherStatement(cypher=cypher, params={"pid": project_id, "rows": rows}, kind="entity_merge")
        )

    # 2) 타입 라벨 부여 (타입별로 문 1개, 라벨만 식별자 삽입)
    for type_label, names in _entity_types(extraction).items():
        tlabel = escape_identifier(type_label, "엔티티 타입 라벨")
        cypher = (
            "UNWIND $names AS nm "
            f"MATCH (n:{base} {{_project: $pid, _name: nm}}) "
            f"SET n:{tlabel}"
        )
        stmts.append(
            CypherStatement(cypher=cypher, params={"pid": project_id, "names": names}, kind="entity_type")
        )

    # 3) 관계 MERGE (관계타입별로 문 1개, 관계타입만 식별자 삽입).
    #    같은 (source,type,target)은 한 UNWIND에서 같은 엣지를 대상으로 하므로, 미리
    #    중복 제거해 설명이 비결정적으로 덮어써지지 않게 한다(첫 등장 유지, 빈 설명이면
    #    이후의 비어있지 않은 설명으로 승격).
    dedup: "OrderedDict[tuple[str, str, str], dict]" = OrderedDict()
    for r in extraction.relations:
        key = (r.type, r.source, r.target)
        if key not in dedup:
            dedup[key] = {"source": r.source, "target": r.target, "description": r.description}
        elif r.description and not dedup[key]["description"]:
            dedup[key]["description"] = r.description
    rel_by_type: "OrderedDict[str, list[dict]]" = OrderedDict()
    for (rtype_name, _s, _t), row in dedup.items():
        rel_by_type.setdefault(rtype_name, []).append(row)
    for rel_type, rows in rel_by_type.items():
        rtype = escape_identifier(rel_type, "관계타입")
        cypher = (
            "UNWIND $rows AS row "
            f"MATCH (a:{base} {{_project: $pid, _name: row.source}}) "
            f"MATCH (b:{base} {{_project: $pid, _name: row.target}}) "
            f"MERGE (a)-[rel:{rtype}]->(b) "
            "SET rel.description = CASE WHEN row.description <> '' "
            "THEN row.description ELSE coalesce(rel.description, '') END"
        )
        stmts.append(
            CypherStatement(cypher=cypher, params={"pid": project_id, "rows": rows}, kind="relation")
        )

    return stmts
