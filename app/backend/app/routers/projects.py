"""/api/projects/* 라우터 (v2, N4).

프로젝트 CRUD + 지식 추출(미리보기) + 병합(ingest) + 그래프 조회.
Neo4j 연결 불가는 503으로 변환한다. extract는 Claude를 호출(과금)하며 우아하게 열화한다.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field, field_validator

from ..claude_extractor import extract
from ..cypher_builder import assert_read_only_cypher
from ..models import Extraction, _clean_label_or_type, _clean_value
from ..ontology_normalizer import canonicalize_extraction, validate_domain_range
from ..neo4j_service import (
    Neo4jUnavailable,
    create_project,
    delete_entity,
    delete_project,
    delete_relation,
    fetch_project_graph,
    get_project,
    ingest,
    list_projects,
    run_read_query,
)
from ..text_to_cypher import generate_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class IngestResponse(BaseModel):
    stats: dict[str, Any]
    graph: dict[str, Any]


class ExtractResponse(BaseModel):
    """추출 미리보기 응답. `extraction`은 사용자 편집·ingest 대상이고, `warnings`는 domain/range
    등 정규화 검증 경고다(경고는 관계를 삭제하지 않는다 — 사용자 판단에 맡긴다). `Extraction`
    모델 자체를 오염시키지 않도록 응답 전용 래퍼로 둔다."""

    extraction: Extraction
    warnings: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class QueryResponse(BaseModel):
    """자연어 탐색 결과. cypher/explanation은 항상 채우고(투명성), graph/rows는 실행 성공 시.

    error가 비어있지 않으면 변환·검증·실행 중 문제가 있었다는 뜻(HTTP는 200 — 재질문 유도).
    """

    cypher: str = ""
    explanation: str = ""
    result_kind: str = "none"  # graph | table | none
    graph: dict[str, Any] = Field(default_factory=lambda: {"nodes": [], "links": []})
    rows: list = Field(default_factory=list)
    columns: list = Field(default_factory=list)
    error: str = ""


class EntityRef(BaseModel):
    """엔티티(노드) 삭제 요청. 이름은 ingest(`Entity.name`)와 **동일하게 정제**(NFC+trim,
    제어/포맷/구분자 거부)해야 저장된 `_name`과 일치한다 — 정규화 불일치로 인한 '조용한
    무삭제'를 막는다."""

    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _clean_value(v, "엔티티 이름(name)")


class RelationRef(BaseModel):
    """관계 삭제 요청. source/target은 값, type은 관계타입 식별자로 ingest와 동일하게 정제."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str = Field(min_length=1)

    @field_validator("source", "target")
    @classmethod
    def _v_endpoints(cls, v: str) -> str:
        return _clean_value(v, "관계 끝점 이름(source/target)")

    @field_validator("type")
    @classmethod
    def _v_type(cls, v: str) -> str:
        return _clean_label_or_type(v, "관계타입(relationship type)")


def _svc(fn: Callable, *args, **kwargs):
    """Neo4j 접근을 감싸 ServiceUnavailable(→Neo4jUnavailable)을 503으로 변환."""
    try:
        return fn(*args, **kwargs)
    except Neo4jUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Neo4j 연결 불가: {e}") from e


def _require_project(project_id: str) -> dict:
    p = _svc(get_project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다")
    return p


@router.get("")
def get_projects() -> list[dict]:
    """프로젝트 목록(최신순)."""
    return _svc(list_projects)


@router.post("")
def post_project(req: ProjectCreate) -> dict:
    """프로젝트 생성."""
    return _svc(create_project, req.name, req.description)


@router.delete("/{project_id}")
def delete(project_id: str) -> dict:
    """프로젝트와 그 지식그래프 삭제."""
    return _svc(delete_project, project_id)


@router.post("/{project_id}/extract", response_model=ExtractResponse)
def post_extract(project_id: str, req: ExtractRequest) -> ExtractResponse:
    """지식 문장에서 엔티티/관계 추출(미리보기, Claude 호출/과금). 아직 그래프에 반영 안 함.

    추출 결과는 extractor가 표준 어휘로 정규화한 상태이며, domain/range 위반은 경고로 함께 반환한다.
    """
    _require_project(project_id)
    graph = _svc(fetch_project_graph, project_id)
    names = [n["name"] for n in graph["nodes"]]
    types = sorted({t for n in graph["nodes"] for t in n.get("types", [])})
    extraction = extract(req.text, existing_entities=names, existing_types=types)
    warnings = validate_domain_range(extraction)
    return ExtractResponse(extraction=extraction, warnings=warnings)


@router.post("/{project_id}/ingest", response_model=IngestResponse)
def post_ingest(project_id: str, extraction: Extraction) -> IngestResponse:
    """확인/편집된 추출 결과를 그래프에 병합하고, 갱신된 그래프를 함께 반환.

    사용자가 수동 입력·편집한 별칭도 최종 병합되도록 진입부에서 다시 정규화한다(멱등).
    domain/range 경고는 미리보기(extract) 단계의 '참고용'이므로 여기서 재검증하지 않는다
    (경고는 관계를 막지 않는다는 설계상 의도 — 편집으로 위반을 새로 만들어도 병합은 진행).
    """
    _require_project(project_id)
    extraction = canonicalize_extraction(extraction)
    result = _svc(ingest, project_id, extraction)
    graph = _svc(fetch_project_graph, project_id)
    return IngestResponse(stats=result["stats"], graph=graph)


@router.get("/{project_id}/graph")
def get_graph(project_id: str) -> dict:
    """프로젝트 지식그래프({nodes, links})."""
    _require_project(project_id)
    return _svc(fetch_project_graph, project_id)


@router.post("/{project_id}/query", response_model=QueryResponse)
def post_query(project_id: str, req: QueryRequest) -> QueryResponse:
    """자연어 질문으로 지식그래프를 탐색한다(text-to-cypher, 읽기 전용).

    흐름: 스키마 힌트 수집 → generate_query(Claude 호출/과금) → assert_read_only_cypher(정적
    검증) → run_read_query(READ 트랜잭션 실행) → 그래프/표 반환. 변환 실패·검증 실패·문법/실행
    오류는 200 + error(재질문 유도), Neo4j 연결 불가는 503.
    """
    _require_project(project_id)

    # 스키마 힌트(정확한 라벨·이름 사용 유도) — 기존 그래프 조회 재사용
    graph = _svc(fetch_project_graph, project_id)
    names = [n["name"] for n in graph["nodes"]]
    types = sorted({t for n in graph["nodes"] for t in n.get("types", [])})
    rel_types = sorted({l["type"] for l in graph["links"]})

    out = generate_query(req.question, types=types, rel_types=rel_types, entity_names=names)
    if out is None or not (out.cypher or "").strip():
        return QueryResponse(
            explanation=(out.explanation if out else ""),
            result_kind=(out.result_kind if out else "none"),
            error="질문을 Cypher로 변환하지 못했습니다. Claude 키가 없거나, 질문을 더 구체적으로 바꿔 보세요.",
        )

    cypher = out.cypher.strip()

    # 정적 안전 검증(읽기 전용 · 단일 문 · 프로젝트 격리 $pid)
    try:
        assert_read_only_cypher(cypher)
    except ValueError as e:
        return QueryResponse(
            cypher=cypher, explanation=out.explanation, result_kind=out.result_kind, error=str(e)
        )

    # 실행: READ 트랜잭션. 연결 불가는 503, 문법/실행 오류(쓰기 절이 READ에서 거부되는 경우 포함)는
    # 200 + error로 우아하게 열화(사용자가 질문을 바꿔 재시도).
    try:
        result = run_read_query(project_id, cypher)
    except Neo4jUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Neo4j 연결 불가: {e}") from e
    except Neo4jError as e:
        logger.info("읽기 쿼리 실행 거부/오류: %s", type(e).__name__)
        return QueryResponse(
            cypher=cypher,
            explanation=out.explanation,
            result_kind=out.result_kind,
            error="이 쿼리는 실행할 수 없습니다(문법 오류이거나 읽기 전용이 아님). 질문을 바꿔 다시 시도해 주세요.",
        )

    return QueryResponse(
        cypher=cypher,
        explanation=out.explanation,
        result_kind=out.result_kind,
        graph=result["graph"],
        rows=result["rows"],
        columns=result["columns"],
    )


@router.delete("/{project_id}/entities", response_model=IngestResponse)
def delete_entity_route(project_id: str, ref: EntityRef) -> IngestResponse:
    """지식 현황에서 노드 1개 삭제(연결된 관계도 함께 제거). 갱신된 그래프를 반환."""
    _require_project(project_id)
    stats = _svc(delete_entity, project_id, ref.name)
    graph = _svc(fetch_project_graph, project_id)
    return IngestResponse(stats=stats, graph=graph)


@router.delete("/{project_id}/relations", response_model=IngestResponse)
def delete_relation_route(project_id: str, ref: RelationRef) -> IngestResponse:
    """지식 현황에서 관계 1개 삭제(끝점 노드는 유지). 갱신된 그래프를 반환."""
    _require_project(project_id)
    stats = _svc(delete_relation, project_id, ref.source, ref.target, ref.type)
    graph = _svc(fetch_project_graph, project_id)
    return IngestResponse(stats=stats, graph=graph)
