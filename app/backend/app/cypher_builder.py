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

import re
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


# ==================================================================
# v2 읽기 경로(text-to-cypher): LLM 생성 Cypher의 정적 안전 검증 — 순수 함수
# ==================================================================

# 읽기 전용 위반으로 간주하는 절/프로시저 키워드(대문자·단어 경계로 검사).
#
# 이 정적 검사는 **조기 거부 + 명확한 한글 에러**를 위한 1차 방어선이다. 실제 쓰기 차단의
# 주 방어선은 neo4j_service가 READ access mode(session.execute_read) 트랜잭션으로만
# 실행한다는 점이다 — 블랙리스트는 원리상 우회 가능성이 있으므로 access mode가 실질
# 방어선이다(CLAUDE.md 불변식 §3의 '사용자/LLM 문자열' 규약을 읽기 경로로 확장).
#
# CALL은 읽기 프로시저(db.labels 등)도 있지만 apoc/db/dbms 쓰기·부작용 위험이 커서 전면
# 차단한다(탐색은 순수 MATCH/WHERE/RETURN으로 충분). LOAD는 LOAD CSV, CREATE는 CREATE
# INDEX/CONSTRAINT까지 포괄한다.
_WRITE_KEYWORDS: tuple[str, ...] = (
    "CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DETACH", "DROP",
    "FOREACH", "LOAD", "CALL", "USE",
)

# 프로젝트 격리 필터에 반드시 등장해야 하는 요소. 실행 시 {"pid": project_id}만 바인딩하므로
# LLM은 $pid를 써야 하고, 값은 문자열 삽입이 아니라 파라미터로만 들어간다. $pid는 단어 경계로
# 검사해 substring 우회($pidding 등)를 막고, _project 속성 참조도 함께 강제한다.
#
# 주의(설계 한계): LLM이 만든 Cypher로 프로젝트 격리를 '검증'하는 것은 원리적으로 불완전하다
# (UNION의 다른 leg, 필터 없는 추가 MATCH 등을 정적으로 다 막긴 어렵다). 이 정적 검사는 흔한
# 실수·우회를 조기 차단하는 보조선이고, **실질 격리 방어선은 neo4j_service의 결과 사후 필터**
# (그래프 노드/관계 + rows 스칼라 모두 _project != project_id를 드롭)다.
_PID_PARAM_RE = re.compile(r"\$pid(?![0-9A-Za-z_$])")
_PROJECT_PROP = "_project"


def _mask_literals(cypher: str) -> str:
    """문자열 리터럴('...', "...")·백틱 식별자(`...`)·주석(//, /* */) 내부를 공백으로 치환한
    스캔용 사본.

    이 구간들 안의 키워드/세미콜론/$pid/_project가 검사에서 오탐(예: `RETURN '삭제'`)되거나
    반대로 우회(예: 주석 `// $pid`로 격리 검사를 만족시키기)되지 않도록, 검사 전에 무력화한다.
    길이·인덱스는 보존(공백 치환). Cypher 문자열 이스케이프는 백슬래시(`\\'`), 백틱 이스케이프는
    두 개(``)로 처리한다.
    """
    out: list[str] = []
    i, n = 0, len(cypher)
    while i < n:
        c = cypher[i]
        if c in ("'", '"'):
            quote = c
            out.append(" ")
            i += 1
            while i < n:
                if cypher[i] == "\\" and i + 1 < n:  # 백슬래시 이스케이프 → 두 글자 스킵
                    out.append("  ")
                    i += 2
                    continue
                if cypher[i] == quote:
                    out.append(" ")
                    i += 1
                    break
                out.append(" ")
                i += 1
            continue
        if c == "`":
            out.append(" ")
            i += 1
            while i < n:
                if cypher[i] == "`" and i + 1 < n and cypher[i + 1] == "`":  # `` 이스케이프
                    out.append("  ")
                    i += 2
                    continue
                if cypher[i] == "`":
                    out.append(" ")
                    i += 1
                    break
                out.append(" ")
                i += 1
            continue
        if c == "/" and i + 1 < n and cypher[i + 1] == "/":  # 한 줄 주석 → 줄 끝까지
            while i < n and cypher[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if c == "/" and i + 1 < n and cypher[i + 1] == "*":  # 블록 주석 → */ 까지
            out.append("  ")
            i += 2
            while i < n:
                if cypher[i] == "*" and i + 1 < n and cypher[i + 1] == "/":
                    out.append("  ")
                    i += 2
                    break
                out.append(" ")
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def assert_read_only_cypher(cypher: str) -> None:
    """LLM이 생성한 Cypher가 '읽기 전용 · 단일 문 · 프로젝트 격리($pid)'인지 정적 검증.

    위반 시 ValueError(한글 사유)를 던지고, 통과하면 None을 반환한다. 부수효과·Neo4j
    접근이 없는 순수 함수라 단위테스트로 검증한다(불변식 §2). 검사 순서는 '더 구체적인
    사유부터'가 아니라 결정적(고정)이다.
    """
    if not isinstance(cypher, str) or not cypher.strip():
        raise ValueError("빈 쿼리입니다")

    scan = _mask_literals(cypher)

    # 1) 다중 문 금지: 리터럴 밖의 세미콜론은 끝(trailing) 1개만 허용한다.
    semi = scan.find(";")
    if semi != -1 and scan[semi + 1:].strip():
        raise ValueError("여러 문(세미콜론 구분)은 허용되지 않습니다 — 한 번에 한 쿼리만 실행합니다")

    # 2) 쓰기/DDL/프로시저 키워드 금지(리터럴·백틱은 이미 마스킹됨).
    upper = scan.upper()
    for kw in _WRITE_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper):
            raise ValueError(
                f"읽기 전용(탐색) 쿼리만 허용됩니다 — 금지된 절/프로시저 '{kw}'가 포함돼 있습니다"
            )

    # 3) 프로젝트 격리(보조선): $pid 파라미터(단어 경계)와 _project 속성 참조가 모두 있어야 한다.
    #    실질 방어선은 neo4j_service의 결과 사후 필터다(위 상수 주석 참조).
    if not _PID_PARAM_RE.search(scan):
        raise ValueError(
            "프로젝트 격리를 위해 쿼리에는 $pid 파라미터가 있어야 합니다(예: {_project: $pid})"
        )
    if _PROJECT_PROP not in scan:
        raise ValueError(
            "프로젝트 격리를 위해 쿼리에는 _project 필터가 있어야 합니다(예: {_project: $pid})"
        )
