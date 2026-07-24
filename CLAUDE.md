# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 현재 상태 (반드시 먼저 읽을 것)

이 디렉토리(`K-water/ontology/`)는 **그린필드**다. 현재 존재하는 파일은 `PLAN.md`
**하나뿐**이며, 아직 애플리케이션 코드·`docker-compose.yml`·의존성 매니페스트가 없다.

- **`PLAN.md`가 유일한 사양서(source of truth)다.** 작업 시작 전 반드시 통독할 것.
  아키텍처, 디렉토리 구조, 중간표현 스키마, API 엔드포인트, 마일스톤이 모두 여기 있다.
- 코드가 생기기 전까지, 아래 "명령"들은 **PLAN.md가 규정한 예정 명령**이며 실제로
  실행 가능한 스크립트/파일은 아직 만들어지지 않았다.
- GitHub 저장소 <https://github.com/2JUNSIK/ontology.git>에서 버전 관리한다.
  플랫폼은 Windows 11 + PowerShell.

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
  **단위테스트**(특히 `cypher_builder`·`survey` 매핑, 설계 불변식 §2·§3), **커밋/브랜치**
  타이밍(비밀 커밋 금지, main 직접 작업 지양), **의존성/스캐폴드 정합성**(PLAN.md와 실제
  레이아웃 어긋남), **포트·컨테이너·볼륨 충돌**(§"로컬 Docker/Neo4j 환경").
- **되돌리기 어렵거나 외부로 나가는 작업은 먼저 확인**: 데이터 삭제/덮어쓰기, force push,
  외부 서비스 전송(예: Claude API 대량 호출로 인한 비용) 등은 실행 전에 알리고 확인받는다.
- **불확실하면 단정하지 말고 질문**: 특히 Claude API 파라미터는 §불변식 5대로 `claude-api`
  스킬로 확정한다. 근거 없이 추정하지 말 것.

> 요약: **"내가 빼먹은 점 있으면 알려줘"가 상시 지시다.** 위험·절차·전제의 공백을
> 발견하면 사용자가 묻지 않아도 먼저 꺼내라.

## 무엇을 만드는가 (빅픽처)

K-water 수자원 도메인(특히 **녹조 관리 / 수질오염 대응**) 지식을 가진 직원이, 온톨로지
이론을 몰라도 설문 답변만으로 **Neo4j 온톨로지(그래프 모델)를 설계**하도록 돕는 웹앱.
"구조화 설문 + Claude LLM 보강" **하이브리드 엔진**이 핵심 차별점이다.

**end-to-end 데이터 흐름 (이 순서가 아키텍처의 뼈대):**
```
설문 답변 → survey.py(규칙: 답변→draft 스키마) → claude_enricher.py(Claude 보강 제안)
  → 사용자 검토/편집 → cypher_builder.py(스키마 JSON→Cypher) → Neo4j 반영 → GraphView 시각화
```
6단계 파이프라인은 PLAN.md §1 참조. MVP는 이 파이프라인 1개를 완성하는 것이 목표.

## 반드시 지켜야 할 설계 불변식 (여러 파일에 걸친 규약)

1. **단일 중간표현(Single Source of Truth)**: `backend/app/models.py`의 Pydantic
   `OntologySchema`(NodeLabel/RelationshipType/PropertyDef)가 설문·Claude·Neo4j·프론트
   전부가 공유하는 유일한 표현이다. 프론트 `types.ts`는 이 모델과 1:1 대응시킨다. 새 필드는
   반드시 이 모델에서 시작해 양쪽으로 전파한다.
2. **`cypher_builder.py`는 순수 함수**: 스키마 JSON → Cypher 문자열 변환은 부수효과 없이
   구현하고 단위테스트로 검증한다. Neo4j 실행은 `neo4j_service.py`가 담당(관심사 분리).
3. **Cypher 인젝션 방지**: 라벨/관계타입 같은 DDL 식별자는 **화이트리스트 검증 + 백틱**
   처리, 값은 반드시 파라미터 바인딩(`$param`). DDL에 사용자 문자열을 직접 끼워넣지 말 것.
4. **스키마 메타 vs 인스턴스 데이터 분리**: 설계된 스키마 자체는 `:_Schema` 메타노드로,
   실제 도메인 인스턴스는 일반 라벨 노드로 저장한다.
5. **Claude 호출(`claude_enricher.py`)**: 반드시 **`claude-api` 스킬**을 사용해 SDK 호출
   형태(모델 ID, 구조화 출력, prompt caching 프리픽스)를 확정한다. API 파라미터를 임의로
   단정하지 말 것. 기본 모델은 `claude-opus-4-8`. 안정 프리픽스(시스템 지침 + 시드
   온톨로지 + 도메인 가이드)에 `cache_control`을 적용하고 가변 서픽스(설문 답변 + draft)를
   분리한다. 출력은 `EnrichmentResponse`로 **구조화 강제**.
6. **비밀키**: `ANTHROPIC_API_KEY`는 백엔드에서만 사용(프론트 노출 금지). `.env`는
   gitignore, `.env.example` 제공.

## 기술 스택 / 예정 명령 (PLAN.md §9)

- 백엔드: Python **FastAPI** (neo4j python driver + anthropic SDK), 포트 8000.
- 프론트: **React + Vite** (그래프 시각화 `react-force-graph`), 포트 5173.
- Neo4j: 로컬 **Docker** `neo4j:5-community`, `bolt://localhost:7687`, 브라우저 7474.

스캐폴드가 생긴 뒤의 실행(앱은 `app/` 하위에 배치하기로 결정됨):
```powershell
# 0) Neo4j (Docker Desktop이 꺼져 있으면 먼저 기동)
cd app; docker compose up -d
# 1) 백엔드
cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt; uvicorn app.main:app --reload --port 8000
# 2) 프론트
cd ..\frontend; npm install; npm run dev
# 단위테스트 (핵심): cypher_builder(스키마→Cypher, 인젝션 방지), survey 매핑 규칙
cd app\backend; pytest
```
> 참고: PLAN.md 원문 §2/§9는 앱 루트를 `ontology-builder/`로 표기하나, 최신 결정은
> **`ontology/app/`** 하위 배치(PLAN.md와 문서는 `ontology/` 루트 유지)다. 코드 스캐폴드
> 시 이 레이아웃을 따르고, PLAN.md의 해당 표기도 함께 정합화할 것.

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

시드 온톨로지와 Claude 프롬프트 프리픽스에 쓰이는 핵심 도메인 사실:
- 조류경보제 임계값(남조류세포수): 관심 ≥1,000 / 경계 ≥10,000 / 대발생 ≥1,000,000 cells/mL.
- 핵심 노드: 저수지, 측정소, 수질항목(클로로필-a·남조류세포수·T-P·T-N·DO·수온 등),
  측정값(측정소·항목·시각을 잇는 이벤트 노드), 조류경보, 오염원, 대응조치, 기관.
- 모델링 포인트: 측정값은 별도 이벤트 노드로 분리(측정소×항목×시각). 새 스키마 제안 시 이
  패턴을 유지·권장할 것.
