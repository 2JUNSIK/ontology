"""FastAPI 진입점.

  - M2: routers.survey (/api/survey/*), routers.schema (/api/suggest)
  - M4: routers.schema 확장 (/api/schema, /api/schema/commit), routers.graph (/api/graph)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import schema as schema_router
from .routers import survey as survey_router

app = FastAPI(title="Ontology Builder API", version="0.2.0")

# 프론트(Vite dev 서버)에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(survey_router.router)
app.include_router(schema_router.router)


@app.get("/health")
def health() -> dict:
    """스모크용 헬스체크."""
    return {"status": "ok", "neo4j_uri": settings.neo4j_uri}
