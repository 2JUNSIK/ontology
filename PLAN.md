# 온톨로지 설계 웹앱 (Ontology Builder) — MVP 구현 계획

## Context (배경)

K-water의 수자원 도메인(특히 **녹조 관리 / 수질오염 대응**) 지식을 가진 직원들이,
질문/답변을 통해 Neo4j 온톨로지(그래프 모델: 노드·관계·속성)를 **직접 설계**하도록
도와주는 웹 애플리케이션을 만든다. 직원은 온톨로지 이론을 몰라도, 구조화된 설문에
답하고 자연어로 도메인을 설명하면 앱이 "노드는 이렇게, 관계는 이렇게 설계하세요"를
제안한다. 최종 설계는 Neo4j에 반영되고 화면에 그래프로 시각화(서빙)된다.

**해결하려는 문제**: 온톨로지/그래프 모델링은 전문 기술인데, 정작 도메인 지식은
현장 직원에게 있다. 이 간극을 "설문 + LLM 보강" 하이브리드로 메운다.

**현재 디렉토리 상태**: 이 앱 전용으로 따로 만든 `K-water/ontology/` 디렉토리에서
구축한다(현재 `PLAN.md`·`CLAUDE.md`만 존재하는 그린필드). 앱 소스는 하위 `app/`에
배치하고 문서는 `ontology/` 루트에 둔다. `causal_inference/`는 `K-water/` 아래 형제
디렉토리로 이 앱과 무관.

**소스 관리**: GitHub 저장소 <https://github.com/2JUNSIK/ontology.git>에서 버전 관리한다.

## 확정된 결정 (사용자 선택)

- **설계 엔진 = 하이브리드**: (1) 구조화 설문 마법사로 뼈대(엔티티·관계·속성)를 잡고,
  (2) Claude API가 자연어 답변을 분석해 누락된 노드/관계/속성을 보강·검증 제안.
- **스택**: 백엔드 Python **FastAPI** (neo4j python driver + anthropic SDK),
  프론트 **React** (그래프 시각화 `react-force-graph`).
- **Neo4j**: 로컬 **Docker** (`neo4j:5-community` — 로컬에 이미 캐시됨, 재다운로드 불필요;
  `bolt://localhost:7687`). compose 프로젝트명/볼륨명을 `ontology-builder` 계열로 분리해
  기존 `genesis`·`cvat` 스택과 충돌 방지. 7474/7687 포트는 현재 사용 가능.
- **범위**: 동작하는 **MVP 우선** — 핵심 파이프라인 1개를 end-to-end로 완성.
- **환경**: Windows 11, PowerShell.

---

## 1. 아키텍처 & 데이터 흐름

```
[React 프론트]                    [FastAPI 백엔드]                  [외부]
 SurveyWizard  ──답변──▶  /api/suggest ──▶ survey.py (규칙: 답변→draft 스키마)
                                        └─▶ claude_enricher.py ──▶ Anthropic API
 SchemaReview ◀─제안+draft─  EnrichmentResponse(보강 제안 JSON)
   (검토·수정)  ──확정 스키마──▶ /api/schema (PUT)
                            ──▶ /api/schema/commit ──▶ cypher_builder.py ─Cypher─▶ Neo4j
 GraphView   ◀──그래프 데이터── /api/graph ◀──────────────────────────────── Neo4j
```

핵심 흐름 6단계:
1. 직원이 설문에 답변(선택+자연어) → 2. `survey.py`가 규칙 기반으로 **draft 스키마**
생성 → 3. `claude_enricher.py`가 draft+답변을 Claude에 보내 **보강 제안** 수신 →
4. 사용자가 프론트에서 제안 수락/거부/편집 → 5. 확정 스키마를 `cypher_builder.py`가
Cypher(제약·인덱스·메타노드)로 변환해 Neo4j 반영 → 6. `/api/graph`로 조회해 시각화.

## 2. 디렉토리 구조

```
ontology/                         # 현재 디렉토리 (문서 루트 = git 저장소 루트)
├─ PLAN.md
├─ CLAUDE.md
├─ .gitignore
└─ app/
   ├─ docker-compose.yml          # name: ontology-builder, neo4j:5-community(7474/7687), 볼륨 ontology_neo4j_data
   ├─ .env.example                # ANTHROPIC_API_KEY, NEO4J_URI/USER/PASSWORD
   ├─ README.md                   # 실행 방법
   ├─ backend/
   │  ├─ requirements.txt         # fastapi, uvicorn, neo4j, anthropic, pydantic, python-dotenv
   │  ├─ app/
   │  │  ├─ main.py               # FastAPI 앱 + CORS + 라우터 등록
   │  │  ├─ config.py             # 환경변수 로드 (pydantic-settings)
   │  │  ├─ models.py             # ★ 공통 중간표현 (OntologySchema 등 Pydantic)
   │  │  ├─ seed_ontology.py      # ★ 녹조/수질 시드 온톨로지 (도메인 가이드 포함)
   │  │  ├─ survey.py             # 설문 문항 정의 + 답변→draft 규칙
   │  │  ├─ claude_enricher.py    # ★ Anthropic 호출 (prompt caching + 구조화 출력)
   │  │  ├─ cypher_builder.py     # ★ 스키마 JSON → Cypher (순수 함수, 테스트 용이)
   │  │  ├─ neo4j_service.py      # driver 세션 관리 + commit/query 실행
   │  │  └─ routers/
   │  │     ├─ survey.py          # /api/survey/*
   │  │     ├─ schema.py          # /api/schema, /api/suggest, /api/schema/commit
   │  │     └─ graph.py           # /api/graph
   │  └─ tests/                   # cypher_builder, survey 규칙 단위테스트
   └─ frontend/
      ├─ package.json             # react, vite, react-force-graph, axios
      └─ src/
         ├─ api.ts                # 백엔드 클라이언트
         ├─ types.ts              # OntologySchema TS 타입 (models.py와 대응)
         ├─ App.tsx               # 3단계 스텝퍼
         └─ components/
            ├─ SurveyWizard.tsx   # 설문 단계
            ├─ SchemaReview.tsx   # 제안 카드 + 스키마 편집
            └─ GraphView.tsx      # ★ react-force-graph 시각화
```

## 3. 공통 중간표현 (Single Source of Truth)

설문·Claude·Neo4j·프론트가 모두 공유하는 스키마 표현. `backend/app/models.py` (Pydantic):

```python
class PropertyDef(BaseModel):
    name: str; type: Literal["string","int","float","date","boolean"]
    required: bool = False; description: str = ""

class NodeLabel(BaseModel):
    label: str                      # 예: "측정소"
    properties: list[PropertyDef]
    key_property: str | None        # UNIQUE 제약 대상 (예: "측정소코드")
    description: str = ""

class RelationshipType(BaseModel):
    type: str                       # 예: "측정"  → (:측정소)-[:측정]->(:수질항목)
    start_label: str; end_label: str
    properties: list[PropertyDef] = []
    description: str = ""

class OntologySchema(BaseModel):
    nodes: list[NodeLabel]
    relationships: list[RelationshipType]

# Claude 보강 제안 (구조화 출력용)
class Suggestion(BaseModel):
    kind: Literal["add_node","add_relationship","add_property","warning"]
    target: str; rationale: str
    payload: dict                    # 제안된 NodeLabel/Relationship/Property
class EnrichmentResponse(BaseModel):
    suggestions: list[Suggestion]
    summary: str
```

## 4. 하이브리드 엔진 상세

### (a) 설문 문항 (녹조/수질 도메인, `survey.py`)
예시 8문항 — 선택형 + 자유서술형 혼합:
1. 관리 대상 물리 자산은? (저수지/보/취수장/정수장 …다중선택)
2. 수질을 어디서 측정하나요? (측정소 개념 유무)
3. 어떤 수질 항목을 관측하나요? (클로로필-a, 남조류세포수, T-P, T-N, DO, 수온 …)
4. 조류경보제를 운영하나요? (관심/경계/대발생 단계)
5. 오염원을 추적하나요? (점오염원/비점오염원)
6. 어떤 대응조치를 하나요? (조류제거선, 살수, 방류량 조절 …)
7. 관련 기관·조직은? (유역환경청, 지자체, 물관리센터 …)
8. (자유서술) 위에서 다루지 못한 중요한 개념/관계를 설명해 주세요.

→ 규칙: 선택된 항목을 `seed_ontology`의 대응 노드/관계로 매핑해 **draft 스키마** 생성.

### (b) Claude 보강 (`claude_enricher.py`)
- 입력: `설문 답변(자유서술 포함) + 현재 draft 스키마 JSON`.
- 출력: `EnrichmentResponse` (구조화 출력으로 강제).
- 역할: 누락 노드/관계/속성 제안, 모델링 경고(예: "측정소와 수질항목 사이 관계 누락",
  "측정값은 측정소·항목·시각을 잇는 별도 노드로 분리 권장").
- **prompt caching**: 안정 프리픽스(시스템 지침 + 시드 온톨로지 + 도메인 모델링 가이드)
  와 가변 서픽스(설문 답변 + draft)를 분리. 프리픽스에 `cache_control` 적용.
- **구현 시 `claude-api` 스킬을 사용해 정확한 SDK 호출 형태(모델 ID, 구조화 출력 방식,
  캐시 프리픽스 최소 토큰, thinking/effort 옵션)를 확정한다.** 계획 단계에서 API 파라미터를
  단정하지 않고, 최신 SDK 규약에 맞춰 구현한다. 기본 모델은 `claude-opus-4-8`.

## 5. FastAPI 엔드포인트

| 메서드 | 경로 | 요청 | 응답 |
|---|---|---|---|
| GET | `/api/survey/questions` | – | 설문 문항 목록 |
| POST | `/api/suggest` | `{answers}` | `{draft: OntologySchema, enrichment: EnrichmentResponse}` |
| GET | `/api/schema` | – | 현재 세션 스키마 |
| PUT | `/api/schema` | `OntologySchema` | 저장된 스키마 (사용자 편집 반영) |
| POST | `/api/schema/commit` | `OntologySchema` | `{applied_cypher: [...], stats}` — Neo4j 반영 |
| GET | `/api/graph` | – | `{nodes, links}` (시각화용) |

MVP는 인메모리 세션(단일 사용자) 또는 Neo4j `:_Schema` 메타노드에 스키마 저장.

## 6. Neo4j 반영 전략 (`cypher_builder.py` + `neo4j_service.py`)

- **스키마 메타 vs 인스턴스 데이터 분리**: 설계된 스키마 자체는 `:_Schema` 라벨의
  메타노드로 저장(무엇을 설계했는지 기록). 실제 도메인 인스턴스(개별 저수지 등)는
  일반 라벨 노드로 별도 관리 (MVP에서는 스키마 반영 + 소량 예시 인스턴스까지).
- **DDL 생성**: 각 `NodeLabel.key_property`에 대해
  `CREATE CONSTRAINT ... IF NOT EXISTS FOR (n:Label) REQUIRE n.key IS UNIQUE`,
  자주 조회되는 속성엔 인덱스.
- **인젝션 방지**: 라벨/관계타입 등 DDL 식별자는 **화이트리스트 검증 + 백틱** 처리,
  값 바인딩은 반드시 파라미터(`$param`) 사용. `cypher_builder`는 순수 함수로 만들어
  단위테스트로 생성 Cypher를 검증.

## 7. 프론트 화면 (3단계 스텝퍼)

1. **SurveyWizard** — 설문 문항 렌더링(체크박스/드롭다운/텍스트), 답변 수집 → `/api/suggest`.
2. **SchemaReview** — 좌: draft 스키마(노드·관계 리스트, 인라인 편집/삭제/추가),
   우: Claude 제안 카드(수락/거부 버튼, 근거 표시). 확정 시 `/api/schema` PUT → commit.
3. **GraphView** — `react-force-graph`로 `/api/graph` 결과 시각화(노드 라벨별 색상,
   관계 타입 라벨, 노드 클릭 시 속성 패널).

## 8. 시드 온톨로지 (녹조/수질오염 대응 도메인, `seed_ontology.py`)

**노드 라벨(예)**:
- `저수지`(명칭, 위치, 저수량), `측정소`(측정소코드, 명칭, 위경도),
  `수질항목`(항목명, 단위) — 클로로필-a(μg/L), 남조류세포수(cells/mL), T-P, T-N,
  DO, 수온, pH, COD, BOD,
- `측정값`(값, 측정시각) — 측정소·항목·시각을 잇는 이벤트 노드,
- `조류경보`(단계, 발령일, 해제일) — 관심/경계/대발생,
- `오염원`(유형: 점/비점, 명칭), `대응조치`(조치유형, 시행일),
- `기관`(기관명, 유형: 유역환경청/지자체/물관리센터).

**관계 타입(예)**:
- `(:측정소)-[:위치]->(:저수지)`
- `(:측정소)-[:측정]->(:수질항목)`, `(:측정값)-[:항목]->(:수질항목)`,
  `(:측정값)-[:관측지점]->(:측정소)`
- `(:저수지)-[:발령]->(:조류경보)`, `(:조류경보)-[:근거지표]->(:수질항목)`
- `(:오염원)-[:유입]->(:저수지)`, `(:대응조치)-[:대상]->(:저수지)`
- `(:기관)-[:관할]->(:저수지)`, `(:기관)-[:시행]->(:대응조치)`

**도메인 실무 반영(조류경보제 기준, 남조류세포수)**: 관심 ≥1,000 / 경계 ≥10,000 /
대발생 ≥1,000,000 cells/mL. 이 임계값은 시드 데이터/가이드에 주석으로 포함해 Claude
보강 프롬프트의 프리픽스로도 활용.

## 9. 로컬 실행 (PowerShell)

```powershell
# 0) Docker Desktop이 꺼져 있으면 먼저 기동 (AutoStart=off) — 데몬 준비까지 대기
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
# Neo4j 기동 (neo4j:5-community 이미지 캐시됨 → 즉시 기동)
cd app; docker compose up -d
# 1) 백엔드 (.env 준비: ANTHROPIC_API_KEY, NEO4J_*)
cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
# 2) 프론트
cd ..\frontend; npm install; npm run dev   # http://localhost:5173
```
- 환경변수는 `.env`(gitignore) 로 관리, `.env.example` 제공. `ANTHROPIC_API_KEY`는
  백엔드에서만 사용(프론트 노출 금지).

## 10. 구현 마일스톤 (순서)

- **M0** 스캐폴드: `app/` 디렉토리, docker-compose(name/볼륨 분리), requirements/package.json.
  Docker Desktop 기동 후 `docker compose up`(neo4j:5-community 캐시 사용, 즉시 기동)로
  7474/7687 Neo4j 접속 확인 — 기존 `genesis`·`cvat` 스택과 포트·볼륨 충돌 없는지 점검.
- **M1** `models.py` + `seed_ontology.py` (공통 표현 + 도메인 시드). *(선행 필수)*
- **M2** `survey.py`: 설문 문항 + 답변→draft 규칙, `/api/survey/*`, `/api/suggest`(Claude 제외 draft만).
- **M3** `claude_enricher.py`: Claude 보강 붙이기 (`claude-api` 스킬로 SDK 확정).
- **M4** `cypher_builder.py` + `neo4j_service.py` + `/api/schema/commit`, `/api/graph` (단위테스트 포함).
- **M5** 프론트 `SurveyWizard` → `SchemaReview` → `GraphView` 연결.
- **M6** end-to-end 통합 확인 + 다듬기(에러 처리, 로딩 상태).

M3/M4는 M2 이후 병렬 가능.

## 검증 (Verification)

end-to-end 스모크 테스트:
1. (Docker Desktop 기동 후) `cd app; docker compose up -d` → `http://localhost:7474`에서
   Neo4j 로그인 확인. 다른 실행 중 스택(cvat 등)과 포트(7474/7687)·볼륨 충돌 없는지 확인.
2. 백엔드 기동 후 `GET /api/survey/questions` 200 확인 (`/docs` Swagger UI 활용).
3. 프론트에서 설문(예: 저수지+측정소+클로로필-a+조류경보 선택, 자유서술에
   "측정소마다 매일 수질 측정값이 쌓인다" 입력) → `/api/suggest` 호출 →
   draft 스키마 + Claude 제안(예: `측정값` 이벤트 노드 분리 제안)이 화면에 표시되는지.
4. 제안 수락/편집 후 commit → Neo4j 브라우저에서 `CALL db.schema.visualization()`으로
   제약조건/라벨 생성 확인.
5. `GraphView`에서 노드·관계가 시각화되는지, 노드 클릭 시 속성 표시되는지.
- 단위테스트: `cypher_builder`(스키마 JSON→기대 Cypher, 인젝션 방지), `survey` 매핑 규칙.

## MVP 이후 확장 여지

사용자 인증/다중 사용자, 스키마 버전 관리·이력, 팀 협업(제안 코멘트),
대량 인스턴스 데이터 적재, Claude Batches/Files API 활용, 프롬프트 캐시 pre-warm,
설계 결과 export(Cypher 스크립트/JSON).
