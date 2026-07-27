"""FastAPI 진입점.

  - v2: routers.projects (/api/projects/*) — 프로젝트 기반 지식그래프 빌더.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .neo4j_service import close_driver
from .routers import projects as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 특별한 준비 없음(드라이버는 최초 요청에 지연 초기화).
    yield
    # 종료 시 Neo4j 드라이버 정리.
    close_driver()


app = FastAPI(title="Ontology Builder API", version="0.4.0", lifespan=lifespan)

# 프론트(Vite dev 서버)에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(projects_router.router)  # v2: 프로젝트 기반 지식그래프


@app.get("/health")
def health() -> dict:
    """스모크용 헬스체크."""
    return {"status": "ok", "neo4j_uri": settings.neo4j_uri}
