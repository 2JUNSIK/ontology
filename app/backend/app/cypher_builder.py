"""스키마 JSON → Cypher 변환 (M4).

설계 불변식(CLAUDE.md / PLAN.md §6):
- **§2 순수 함수**: `OntologySchema` → Cypher 문(+파라미터). 부수효과·Neo4j 접근 없음.
  실제 실행은 `neo4j_service`가 담당(관심사 분리). 그래서 단위테스트로 생성물을 검증 가능.
- **§3 인젝션 방지**: 라벨/관계타입/키 같은 **DDL 식별자**는 화이트리스트(`_clean_identifier`)
  재검증 + 백틱 이스케이프. 값·문자열은 전부 **파라미터 바인딩(`$param`)**. 사용자 문자열을
  DDL에 직접 끼워넣지 않는다.
- **§4 스키마 메타 vs 인스턴스 분리**: 설계된 스키마 자체는 `:_Schema` 메타노드 +
  `:_SCHEMA_REL` 메타관계로 저장한다. 실제 도메인 인스턴스(측정소 개별 노드 등)는 여기서
  다루지 않는다(일반 라벨로 별도 관리).

메타 그래프 표현(시각화용):
- 각 `NodeLabel` → `(:_Schema {label, description, key_property, properties_json})`.
- 각 `RelationshipType` → 두 메타노드 사이의 `(:_Schema)-[:_SCHEMA_REL {rel_type,...}]->(:_Schema)`.
  도메인 관계타입은 **고정 관계타입 `_SCHEMA_REL`의 속성(`rel_type`)** 으로 저장한다
  (동적 관계타입을 DDL에 끼워넣지 않기 위함 — 인젝션 표면 제거).
"""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field

from .models import Extraction, OntologySchema, PropertyDef, _clean_identifier

# 스키마 메타 저장에 쓰는 예약 식별자(사용자 입력 아님 — 상수).
META_NODE_LABEL = "_Schema"
META_REL_TYPE = "_SCHEMA_REL"

# v2 지식그래프: 모든 지식 노드의 공통 기본 라벨. 정체성은 (_project,_name)로 잡고,
# 도메인 타입은 이 위에 라벨로 얹는다(다중 라벨). 예: (:_Entity:현상 {_project,_name}).
ENTITY_BASE_LABEL = "_Entity"


@dataclass(frozen=True)
class CypherStatement:
    """실행 단위. neo4j_service가 문/파라미터로 실행하고 kind로 통계를 집계한다."""

    cypher: str
    params: dict = field(default_factory=dict)
    kind: str = ""  # constraint | meta_clear | meta_node | meta_rel


def escape_identifier(ident: str, kind: str = "식별자") -> str:
    """식별자를 재검증(1차 방어선 재확인) 후 백틱 이스케이프(2차 방어선, 불변식 §3).

    `_clean_identifier`가 백틱/제어문자/빈 문자열을 이미 거부하므로 아래 백틱 이중화는
    방어적 중복이다(정상 입력에선 효과 없음). 그래도 유지해 DDL 인젝션 불변식을 국소적으로
    보장한다 — cypher_builder만 봐도 안전함이 명확하도록.
    """
    clean = _clean_identifier(ident, kind)
    return "`" + clean.replace("`", "``") + "`"


def _properties_json(properties: list[PropertyDef]) -> str:
    """속성 목록을 JSON 문자열로 직렬화.

    Neo4j 속성값은 원시값/원시값 배열만 가능해 map 리스트를 그대로 저장할 수 없다.
    따라서 속성 정의는 JSON 문자열로 저장하고, 조회 측(neo4j_service)에서 역직렬화한다.
    ensure_ascii=False로 한글을 그대로 보존한다.
    """
    return json.dumps([p.model_dump() for p in properties], ensure_ascii=False)


def build_constraints(schema: OntologySchema) -> list[CypherStatement]:
    """key_property가 있는 노드마다 UNIQUE 제약 DDL을 만든다(IF NOT EXISTS로 멱등).

    라벨/키는 식별자이므로 파라미터 바인딩이 불가능(Cypher DDL 제약) → 화이트리스트
    재검증 + 백틱 이스케이프로만 안전하게 삽입한다.
    """
    stmts: list[CypherStatement] = []
    for n in schema.nodes:
        if n.key_property is None:
            continue
        label = escape_identifier(n.label, "라벨")
        key = escape_identifier(n.key_property, "key_property")
        cypher = (
            f"CREATE CONSTRAINT IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
        )
        stmts.append(CypherStatement(cypher=cypher, kind="constraint"))
    return stmts


def build_meta_clear() -> CypherStatement:
    """이전에 커밋된 스키마 메타(:_Schema)를 제거한다(재커밋 시 교체).

    주의: `:_Schema` 메타노드/메타관계에만 한정된다. 도메인 인스턴스 노드는 건드리지 않는다.
    """
    label = escape_identifier(META_NODE_LABEL, "메타라벨")
    return CypherStatement(
        cypher=f"MATCH (s:{label}) DETACH DELETE s",
        kind="meta_clear",
    )


def build_meta_nodes(schema: OntologySchema) -> CypherStatement:
    """노드 라벨들을 :_Schema 메타노드로 저장(값은 전부 파라미터 바인딩)."""
    label = escape_identifier(META_NODE_LABEL, "메타라벨")
    rows = [
        {
            "label": n.label,
            "description": n.description,
            "key_property": n.key_property,
            "properties_json": _properties_json(n.properties),
        }
        for n in schema.nodes
    ]
    cypher = (
        "UNWIND $rows AS row "
        f"MERGE (s:{label} {{label: row.label}}) "
        "SET s.description = row.description, "
        "s.key_property = row.key_property, "
        "s.properties_json = row.properties_json"
    )
    return CypherStatement(cypher=cypher, params={"rows": rows}, kind="meta_node")


def build_meta_rels(schema: OntologySchema) -> CypherStatement:
    """관계 타입들을 :_Schema 메타노드 사이의 :_SCHEMA_REL 메타관계로 저장.

    양 끝 라벨을 MERGE 하므로, 노드 목록에 없는 라벨을 참조해도 끊긴 엣지가 되지 않는다
    (설계상 유의점은 OntologySchema.consistency_warnings가 이미 사용자에게 표시).
    도메인 관계타입은 `rel_type` 속성(파라미터)으로 저장 — 동적 관계타입을 DDL에 넣지 않음.
    """
    label = escape_identifier(META_NODE_LABEL, "메타라벨")
    rel = escape_identifier(META_REL_TYPE, "메타관계타입")
    rows = [
        {
            "type": r.type,
            "start_label": r.start_label,
            "end_label": r.end_label,
            "description": r.description,
            "properties_json": _properties_json(r.properties),
        }
        for r in schema.relationships
    ]
    cypher = (
        "UNWIND $rows AS row "
        f"MERGE (a:{label} {{label: row.start_label}}) "
        f"MERGE (b:{label} {{label: row.end_label}}) "
        f"MERGE (a)-[rel:{rel} {{rel_type: row.type}}]->(b) "
        "SET rel.description = row.description, "
        "rel.properties_json = row.properties_json"
    )
    return CypherStatement(cypher=cypher, params={"rows": rows}, kind="meta_rel")


def build_commit_statements(schema: OntologySchema) -> list[CypherStatement]:
    """커밋에 필요한 Cypher 문들을 실행 순서대로 반환(순수 함수).

    실행 순서: 제약(스키마 트랜잭션) → 메타 초기화 → 메타노드 → 메타관계(데이터 트랜잭션).
    각 문은 neo4j_service에서 **개별 트랜잭션**으로 실행되므로, 한 트랜잭션 안에서
    스키마 변경과 데이터 변경이 섞이지 않는다(Neo4j 제약 회피).
    """
    stmts: list[CypherStatement] = []
    stmts.extend(build_constraints(schema))
    stmts.append(build_meta_clear())
    if schema.nodes:
        stmts.append(build_meta_nodes(schema))
    if schema.relationships:
        stmts.append(build_meta_rels(schema))
    return stmts


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
