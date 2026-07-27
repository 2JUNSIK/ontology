# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 현재 상태 (반드시 먼저 읽을 것)

**v2 피벗 완료. 진행: N1~N6 완료** (2026-07-27 기준). 제품이 "구조화 설문형 온톨로지 설계"
(v1)에서 **"자연어 지식 입력형 지식그래프 빌더"**(v2)로 바뀌었다(사용자 요청). 직원이 문장으로
지식을 입력하면 Claude가 엔티티(노드)·관계를 추출해 **프로젝트별 지식그래프에 MERGE 누적**한다.
백엔드+프론트 재작성이 끝나 end-to-end 동작하며, **N6에서 구 v1(설문/스키마) 코드를 완전 제거**해
코드베이스가 v2만 남았다. 다음 작업은 프론트 디자인/기능 확장.

- **`PLAN.md`(v2)가 사양서(source of truth)다.** 작업 전 통독 — 아키텍처, 데이터 모델(§2),
  API(§5), 마일스톤(N1~N6, §10), "진행 현황"이 모두 여기 있다.
- **현재 코드**(`app/backend/app/`):
  - [v2 핵심] `models.py`(Entity/Relation/Extraction + 식별자 방어선), `cypher_builder.py`
    (`build_entity_constraint`/`build_ingest_statements`, `ENTITY_BASE_LABEL`), `neo4j_service.py`
    (프로젝트 CRUD·`ingest`·`fetch_project_graph`), `claude_extractor.py`, `routers/projects.py`,
    `config.py`, `main.py`.
  - [v1 제거 완료(N6)] `survey.py`·`claude_enricher.py`·`routers/{survey,schema,graph}.py`·
    `cypher_builder`의 스키마-메타 함수·`neo4j_service`의 `commit_schema`/`fetch_graph`·
    `models.py`의 v1 모델(OntologySchema/NodeLabel/…)·`seed_ontology.SEED_ONTOLOGY`를 모두 삭제.
    **`seed_ontology.py`의 `DOMAIN_GUIDE`(+임계값·수질항목 상수)는 extractor가 재사용하므로 유지.**
  - 프론트(`app/frontend/src/`): `App.tsx`, `api.ts`, `types.ts`,
    `components/{ProjectList,Workspace,ExtractionPreview,GraphView}.tsx`. (구 `SurveyWizard`/
    `SchemaReview`는 이미 삭제.)
- **명령은 실제로 동작**(venv·node_modules 존재). 개발 중 백엔드(uvicorn :8000)·프론트(vite :5173)
  서버가 백그라운드로 떠 있을 수 있다. **백엔드 코드 변경 시 재시작 필요**(--reload 미사용 시 —
  포트 8000 리스너 kill 후 재기동). 프론트는 Vite HMR로 자동 반영.
- **테스트 63 passed / 7 skipped**(통합은 opt-in). GitHub <https://github.com/2JUNSIK/ontology.git>
  (main 브랜치). Windows 11 + PowerShell.

### 마일스톤마다 지키는 작업 방식 (사용자 상시 지시)
코드 작성 후 **커밋 전에** 적대적 서브에이전트로 코드 검수 + 엣지케이스 테스트를 수행하고,
must-fix를 반영한 뒤 커밋/푸시한다. 재사용 리뷰어는 `.claude/agents/ontology-reviewer.md`
(다음 세션부터 `ontology-reviewer` 타입으로 호출 가능; 당세션 신규 생성 시엔 로드 안 됨 →
범용 에이전트에 동일 지침으로 대체). 커밋 메시지 here-string에 **큰따옴표 금지**
(PowerShell 5.1에서 인자 분할됨).

## 사용자에게 먼저 알려야 할 것 (사전 경고 · 프로세스 가드레일)

사용자는 온톨로지/개발 프로세스 전문가가 아닐 수 있다. **시키는 것만 하지 말고,
놓치기 쉬운 위험·절차·전제를 먼저 짚어주는 것**이 이 프로젝트에서 Claude의 역할이다.
아래 상황에서는 작업을 진행하기 전(또는 직후)에 반드시 사용자에게 알린다.

- **보안 / 비밀키**: 비밀키·비밀번호·토큰이 **채팅·커밋·로그에 평문 노출**되면 즉시
  경고하고 **로테이션(재발급)** 을 권한다. 노출된 비밀은 파일로 옮겨도 "이미 유출된 것"으로
  간주한다. 앞으로 비밀 전달은 채팅 붙여넣기 대신 "`app/.env`에 넣어뒀다"고만 알리게
  안내하고, 값은 화면에 출력하지 말 것(존재·길이·형식만 검증). `.env`가 gitignore되는지
  `git check-ignore`로 확인하고, 새 비밀 항목이 생기면 `.env.example`에 **더미값으로**
  동기화한다.
- **"했다"는 말과 실제 상태가 다를 수 있다**: 사용자가 "저장/수정/실행했다"고 해도 결과를
  **직접 검증**하고, 불일치를 발견하면 추측하지 말고 그대로 알린다(예: `.env` 저장 누락,
  잘못된 위치 편집, 미저장). 조용히 넘어가지 말 것.
- **개발 프로세스 누락 신호**: 다음이 빠졌으면 진행 전에 짚는다 — 핵심 로직 변경 시
  **단위테스트**(특히 `cypher_builder`의 ingest/추출 매핑, 설계 불변식 §2·§3), **커밋/브랜치**
  타이밍(비밀 커밋 금지, main 직접 작업 지양), **의존성/스캐폴드 정합성**(PLAN.md와 실제
  레이아웃 어긋남), **포트·컨테이너·볼륨 충돌**(§"로컬 Docker/Neo4j 환경").
- **되돌리기 어렵거나 외부로 나가는 작업은 먼저 확인**: 데이터 삭제/덮어쓰기, force push,
  외부 서비스 전송(예: Claude API 대량 호출로 인한 비용) 등은 실행 전에 알리고 확인받는다.
- **불확실하면 단정하지 말고 질문**: 특히 Claude API 파라미터는 §불변식 5대로 `claude-api`
  스킬로 확정한다. 근거 없이 추정하지 말 것.

> 요약: **"내가 빼먹은 점 있으면 알려줘"가 상시 지시다.** 위험·절차·전제의 공백을
> 발견하면 사용자가 묻지 않아도 먼저 꺼내라.

## 무엇을 만드는가 (빅픽처)

K-water 수자원 도메인(특히 **녹조 관리 / 수질오염 대응**) 지식을 가진 직원이, 온톨로지 이론을
몰라도 **자연어로 지식을 한 문장씩 입력**하면 Claude가 노드·관계를 추출해 **프로젝트별
지식그래프에 누적**해 주는 웹앱. "자연어 입력 + LLM 추출 + 미리보기 확인"이 핵심.

**end-to-end 데이터 흐름 (v2 아키텍처의 뼈대):**
```
프로젝트 선택 → 지식 문장 입력 → claude_extractor.extract(엔티티·관계 추출)
  → 미리보기/편집(수락·제외) → cypher_builder.build_ingest_statements(MERGE)
  → neo4j_service.ingest(프로젝트 그래프에 병합) → GraphView 누적 시각화 → 반복
```
예: "조류경보제는 관심·경계·대발생 3단계로 운영된다" → `(조류경보제:제도)`,`(관심:경보단계)`…
+ `(조류경보제)-[단계]->(관심)`… 을 그래프에 추가. 같은 개념 재입력 시 MERGE로 병합(누적).
자세한 흐름은 PLAN.md §1 참조.

## 반드시 지켜야 할 설계 불변식 (여러 파일에 걸친 규약)

1. **단일 중간표현(Single Source of Truth)**: `backend/app/models.py`의 Pydantic 모델이
   설문·Claude·Neo4j·프론트가 공유하는 유일한 표현이다. **v2 핵심**: `Entity`(name·type·
   description) / `Relation`(source·target·type·description) / `Extraction`(entities·relations·
   summary). 프론트 `types.ts`는 이 모델과 1:1 대응. 새 필드는 반드시 이 모델에서 시작해 양쪽
   전파. (v1 모델 `OntologySchema`/`NodeLabel`/… 은 N6에서 완전 제거됨 — KG 모델만 존재.)
2. **`cypher_builder.py`는 순수 함수**: JSON→Cypher 변환은 부수효과·Neo4j 접근 없이 구현하고
   단위테스트로 검증한다. 실행은 `neo4j_service.py`가 담당(관심사 분리). v2 진입점은
   `build_ingest_statements(project_id, Extraction)` → `list[CypherStatement]`.
3. **Cypher 인젝션 방지**: **값(엔티티 이름·설명·project_id)은 반드시 파라미터 바인딩(`$param`)**.
   **식별자(타입 라벨·관계타입)는 화이트리스트(`escape_identifier`=`_clean_label_or_type` 재검증)
   + 백틱**. 동적 라벨/관계타입은 UNWIND로 파라미터화할 수 없으므로 **타입별로 그룹핑해 문 하나당
   검증된 식별자 1개만** 삽입한다. 사용자/LLM 문자열을 식별자 위치에 직접 끼워넣지 말 것.
4. **메타 vs 인스턴스 분리 (v2)**: 프로젝트 메타는 `(:_Project {id,name,…})`. 지식 노드는 공통
   기본 라벨 `(:_Entity {_project,_name,description})` + **동적 타입 라벨**(예: `:현상`,`:경보단계`).
   정체성 = **(`_project`,`_name`) 복합 UNIQUE** → 같은 이름 재입력 시 MERGE 병합. 관계는 같은
   프로젝트의 `:_Entity` 사이. **라벨/관계타입은 `_` 프리픽스 금지**(내부/메타 예약 —
   `_clean_label_or_type`가 거부; 값인 이름/설명엔 이 제약 없음).
5. **Claude 호출(`claude_extractor.py`)**: SDK 형태는 **`claude-api` 스킬**로 확정(모델
   `claude-opus-4-8`). `client.messages.parse(output_format=_ExtractionOut)` → `resp.parsed_output`.
   free-form dict 미지원 → 전용 출력 스키마로 받고 내부 `Extraction`으로 **재검증**(타입 라벨/
   관계타입이 `_clean_label_or_type` 방어선을 통과해야 함, 실패 항목은 드롭). 안정 프리픽스
   (지침+`DOMAIN_GUIDE`)에 `cache_control`, 가변부(입력 텍스트+기존 엔티티 힌트)는 user 턴.
   키 없음/빈 입력/실패 시 빈 `Extraction`으로 **우아한 열화**. **비용**: `/api/projects/{id}/extract`가
   매 호출 실제 API를 부른다(프론트에 고지).
6. **비밀키**: `ANTHROPIC_API_KEY`는 백엔드에서만 사용(프론트 노출 금지). `.env`는
   gitignore, `.env.example` 제공.

## 기술 스택 / 명령 (PLAN.md §9)

- 백엔드: Python **3.14** + **FastAPI**, `neo4j` 드라이버 **6.2.0**(6.x API 기준 —
  `execute_query(...,routing_=,database_=)`, `session.run`/`execute_write`, `record.data()`),
  `anthropic` **0.119**, 포트 8000.
- 프론트: **React + Vite**, 그래프 시각화 **`react-force-graph-2d`**(경량 2D 전용), 포트 5173.
- Neo4j: 로컬 **Docker** `neo4j:5-community`(실행 시 5.26 community), `bolt://localhost:7687`,
  브라우저 7474.

실행(스캐폴드/venv/node_modules 존재 — 동작함):
```powershell
# 0) Neo4j (Docker Desktop이 꺼져 있으면 먼저 기동)
cd app; docker compose up -d
# 1) 백엔드 (venv: app\backend\.venv)
cd backend; .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000   # http://localhost:8000/health, /docs
# 2) 프론트
cd ..\frontend; npm install; npm run dev     # http://localhost:5173
```
**테스트(핵심 게이트)** — venv의 python으로 직접 실행하는 것이 확실하다:
```powershell
& "app\backend\.venv\Scripts\python.exe" -m pytest app\backend      # 154 passed / 11 skipped
# Neo4j 통합 테스트는 opt-in(파괴적) — Neo4j 기동 상태에서만:
$env:RUN_NEO4J_TESTS=1; & "app\backend\.venv\Scripts\python.exe" -m pytest app\backend\tests\test_kg_integration.py; Remove-Item Env:\RUN_NEO4J_TESTS
```
- `pytest.ini`가 `pythonpath=.`/`testpaths=tests` 설정. 테스트는 `app.모듈` 로 임포트.
- **`tests/conftest.py`가 모든 테스트에서 실제 Claude 호출을 차단**(autouse로 `ANTHROPIC_API_KEY`
  공백화) + 세션 스키마 리셋. Claude 경로 검증 테스트는 `_make_client`를 모킹한다.
  → 테스트 추가 시 실제 API를 부르지 말 것(비용).
- **통합 테스트는 `RUN_NEO4J_TESTS`로 opt-in**(기본 실행에선 skip). commit/ingest가 데이터를
  쓰므로 파괴적 — 전용 테스트 프로젝트/라벨을 만들고 teardown에서 정리한다.
- **프론트 타입체크**: `cd app/frontend; npx tsc --noEmit`(dev는 esbuild라 타입체크 생략됨).
  파일 저장 시 UTF-8 유지에 주의(과거 Write에서 널 바이트가 섞인 적 있음 → 저장 후 스캔 권장).

## 로컬 Docker / Neo4j 환경 (검증됨 — 재조사 불필요)

이 머신에는 이미 관련 자산이 있으니 새로 받거나 만들기 전에 활용/충돌을 확인할 것:

- **Docker Desktop 설치됨**(WSL2, containerd 스토어)이나 **AutoStart=off** → 사용 전 수동
  기동 필요: `Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"` 후 데몬
  준비 대기.
- **`neo4j:5-community` 이미지가 이미 로컬에 캐시됨**(약 898MB) → `docker compose up`이
  즉시 기동된다(재다운로드 불필요). `neo4j:5.18`도 존재.
- **포트 7474/7687은 현재 비어 있음**(사용 가능). 단 다른 스택(**cvat**: traefik
  8080/8090 등)이 실행 중일 수 있으니 포트 충돌을 점검할 것. 백엔드 8000·프론트 5173은 유휴.
- **이름 충돌 주의**: 기존에 `genesis`(neo4j+fuseki+redis), `ai_project`, `cvat`,
  `waterpipe`, `n8n` 등 다수 컨테이너/볼륨이 존재한다. 새 앱은 compose **프로젝트명**
  (`name: ontology-builder` 권장)과 **볼륨명**(`ontology_neo4j_data` 등)을 명확히 분리해
  기존 자산과 섞이지 않게 할 것.
- **이전 neo4j 데이터**: `genesis_neo4j_data` 볼륨에 과거 작업 데이터가 보존돼 있다.
  MVP는 새 볼륨으로 깨끗이 시작하는 것을 기본으로 하되, 필요 시 이 볼륨을 조회/재사용할 수
  있음을 기억할 것.

## 도메인 참고 (녹조/수질, PLAN.md §8)

`DOMAIN_GUIDE`(seed_ontology.py)가 Claude 추출 프롬프트의 안정 프리픽스로 쓰인다. 핵심 사실:
- 조류경보제 임계값(남조류세포수): 관심 ≥1,000 / 경계 ≥10,000 / 대발생 ≥1,000,000 cells/mL.
- 엔티티 **타입 라벨 예시**: 현상·생물·제도·경보단계·지표·오염원·대응조치·기관·저수지·측정소.
  관계타입 예시: 원인·단계·기준지표·유입·관할·측정.
- 지식그래프는 **인스턴스/개념 수준**(예: `(녹조:현상)`, `(관심:경보단계)`). 같은 이름은
  프로젝트 내에서 MERGE로 하나의 노드로 병합된다.
