"""/api/graph 라우터 (M4).

커밋된 스키마 메타 그래프를 시각화용 {nodes, links}로 반환한다(GraphView 소비).
Neo4j 연결 불가 시 503으로 응답한다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..neo4j_service import Neo4jUnavailable, fetch_graph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
def graph() -> dict:
    """스키마 그래프(노드=라벨, 링크=관계타입)를 반환한다."""
    try:
        return fetch_graph()
    except Neo4jUnavailable as e:
        raise HTTPException(status_code=503, detail=f"Neo4j 연결 불가: {e}") from e
