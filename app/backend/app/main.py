"""FastAPI 진입점 (M0 스캐폴드).

현재는 헬스체크만 제공한다. 이후 마일스톤에서 라우터를 등록한다:
  - M2: routers.survey  (/api/survey/*, /api/suggest)
  - M4: routers.schema  (/api/schema, /api/schema/commit), routers.graph (/api/graph)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

app = FastAPI(title="Ontology Builder API", version="0.1.0")

# 프론트(Vite dev 서버)에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """M0 스모크용 헬스체크."""
    return {"status": "ok", "neo4j_uri": settings.neo4j_uri}
