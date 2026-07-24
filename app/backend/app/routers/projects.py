"""/api/projects/* 라우터 (v2, N4).

프로젝트 CRUD + 지식 추출(미리보기) + 병합(ingest) + 그래프 조회.
Neo4j 연결 불가는 503으로 변환한다. extract는 Claude를 호출(과금)하며 우아하게 열화한다.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..claude_extractor import extract
from ..models import Extraction
from ..neo4j_service import (
    Neo4jUnavailable,
    create_project,
    delete_project,
    fetch_project_graph,
    get_project,
    ingest,
    list_projects,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class IngestResponse(BaseModel):
    stats: dict[str, Any]
    graph: dict[str, Any]


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


@router.post("/{project_id}/extract", response_model=Extraction)
def post_extract(project_id: str, req: ExtractRequest) -> Extraction:
    """지식 문장에서 엔티티/관계 추출(미리보기, Claude 호출/과금). 아직 그래프에 반영 안 함."""
    _require_project(project_id)
    graph = _svc(fetch_project_graph, project_id)
    names = [n["name"] for n in graph["nodes"]]
    types = sorted({t for n in graph["nodes"] for t in n.get("types", [])})
    return extract(req.text, existing_entities=names, existing_types=types)


@router.post("/{project_id}/ingest", response_model=IngestResponse)
def post_ingest(project_id: str, extraction: Extraction) -> IngestResponse:
    """확인/편집된 추출 결과를 그래프에 병합하고, 갱신된 그래프를 함께 반환."""
    _require_project(project_id)
    result = _svc(ingest, project_id, extraction)
    graph = _svc(fetch_project_graph, project_id)
    return IngestResponse(stats=result["stats"], graph=graph)


@router.get("/{project_id}/graph")
def get_graph(project_id: str) -> dict:
    """프로젝트 지식그래프({nodes, links})."""
    _require_project(project_id)
    return _svc(fetch_project_graph, project_id)
