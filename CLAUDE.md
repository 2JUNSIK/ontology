# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 이 저장소의 현재 상태 (반드시 먼저 읽을 것)

**v2 피벗 완료. 진행: N1~N14 완료** (2026-08-05 기준). 제품이 "구조화 설문형 온톨로지 설계"
(v1)에서 **"자연어 지식 입력형 지식그래프 빌더"**(v2)로 바뀌었다(사용자 요청). 직원이 문장으로
지식을 입력하면 Claude가 엔티티(노드)·관계를 추출해 **프로젝트별 지식그래프에 MERGE 누적**한다.
백엔드+프론트 재작성이 끝나 end-to-end 동작한다. **N6**에서 구 v1(설문/스키마) 코드를 완전 제거해
코드베이스가 v2만 남았고, **N7**에서 "지식 현황"(노드·관계 데이터 표 + 개별 삭제 + 페이지네이션)과
세로 레이아웃을 추가했다. **N8**에서 **자연어 그래프 탐색(text-to-cypher, 읽기 경로)** 을 추가해 —
자연어 질문을 Claude가 **읽기전용 Cypher**로 변환→실행→그래프/표로 — 앱이 입력(쓰기)뿐 아니라
**탐색(읽기)** 까지 하는 양방향이 됐다. UI는 Workspace를 상단 **지식설계/지식활용 2개 탭**으로 나눠
입력·관리(설계)와 자연어 탐색(활용)을 분리했고, 상단 브랜드 부제목은 제거했다. **N9**에서
**표준 어휘 정규화**(수자원 운영관리 표준 타입/관계 + 별칭→표준명 canonical화 + domain/range 경고,
순수 후처리 `ontology_normalizer.py`)를, **N10**에서 **정량 속성 구조화**(임계값·대표 수치를
`value/unit/comparator/observed_at` 노드 속성으로 — 자유 텍스트에 묻지 않고 비교·집계 가능하게)를
추가했다("실무형 지식그래프 강화" 방향). **N11**에서 **그래프 시각화를 강화**(degree 비례 노드 크기·
노드 검색/하이라이트·전체보기(zoomToFit)/재정렬·정량값 amber 링, 순수 프론트 `GraphView.tsx`)하고,
**N12**에서 지식활용 탐색에 **예시 질문 프리셋**(클릭 시 질문칸만 채움·자동 실행 안 함, `QueryPanel.tsx`)을
추가했다. **N13**에서 **디자인/UX 리프레시**(다크모드까지 풀 리프레시, 현재 Toss 톤 유지·정제)를 했다 —
`index.css` 토큰을 테마화(`:root[data-theme="dark"]` 오버라이드+글래스/notice 토큰)하고, 공유 UI 프리미티브
`theme.tsx`(ThemeProvider/useTheme)·`ThemeToggle`·`ui/{ConfirmDialog(useConfirm),Toast(useToast),Skeleton}`을
추가해 `window.confirm`→커스텀 모달, 성공 피드백→토스트, 로딩→스켈레톤, 빈 상태 CTA, 비용 배지, 반응형·접근성
(focus-visible·aria·배경 inert·prefers-reduced-motion)을 갖췄다(순수 프론트, API 과금 없음).
**N14**에서 **온톨로지 설명자료**(헤더 우측 '온톨로지란?' → 앱 내 **전체화면 페이지**)를 추가했다 —
교재(그래프DB→지식그래프→온톨로지→GraphRAG)에 **팔란티어 온톨로지·디지털 트윈** 공개자료(공식
docs/blog로 검증)를 더해 이 앱 맥락(녹조/수질 예시 위주 + 급수계통 보조)으로 쉽게 재구성한 직원
교육자료. 신규 `components/OntologyGuide.tsx`(처음 모달로 만들었다가 콘텐츠가 많아 **전체화면
페이지로 전환** — createPortal/inert/focus-trap 제거·onBack/Esc/트리거 포커스 복원), `App.tsx` 헤더에
페이지 토글 버튼(`.help-btn`, aria-pressed), `index.css`에 페이지 셸(`.guide-page/.guide-article/.guide-*`).
내용: ① 그래프/온톨로지 기초·공리와 추론 → ② **팔란티어 심층**(온톨로지=의사결정 모델·semantic 명사 +
kinetic 동사·RAG→OAG·Disruption Bot·재사용 해자) → ③ **디지털 트윈 가설 검토**(관계기반 추론이 핵심,
실시간 상태·행동 보강) → ④ **수자원 트윈 확장 시나리오**(대청호 녹조). 적대적 사실검증·접근성 검수
반영, 순수 프론트·API 과금 없음·tsc/build 통과.
다음: 프론트 디자인/기능 확장 계속.

> **git 상태(2026-08-05)**: **N1~N14 전부 main에 머지·push 완료**(`main`=`origin/main`=`809cf07`).
> N14(온톨로지 설명 페이지)를 `feat-ontology-guide`에서 ff 머지한 뒤 그 피처 브랜치를 **로컬·원격 모두 삭제**. **현재 브랜치는 `main` 하나뿐.**
> `gh` 미설치 → 다음 작업은 새 피처 브랜치에서, PR은 push 후 반환된 웹 링크로 연다. (참조: 메모리 `git-feature-branch-workflow`)

- **`PLAN.md`(v2)가 사양서(source of truth)다.** 작업 전 통독 — 아키텍처, 데이터 모델(§2),
  API(§5), 마일스톤(N1~N14, §10), "진행 현황"이 모두 여기 있다.
- **현재 코드**(`app/backend/app/`):
  - [v2 핵심] `models.py`(Entity/Relation/Extraction + 식별자 방어선 + **정량 속성**
    `value/unit/comparator/observed_at`, comparator 화이트리스트·value NaN/Inf/bool 거부·고아 정량 정규화),
    `cypher_builder.py`(`build_entity_constraint`/`build_ingest_statements`, `ENTITY_BASE_LABEL`,
    entity MERGE에 정량 속성 SET, +읽기경로 `assert_read_only_cypher`),
    **`ontology_normalizer.py`**(N9 순수 함수: `canonicalize_extraction` 별칭·타입 표준화+병합,
    `validate_domain_range` 경고), `neo4j_service.py`(프로젝트 CRUD·`ingest`·`fetch_project_graph`·
    `delete_entity`·`delete_relation`, +읽기경로 `run_read_query`/`_collect_graph`/`_scalarize`),
    `claude_extractor.py`(추출 후 `canonicalize_extraction` 후처리), `text_to_cypher.py`(자연어→읽기전용
    Cypher 생성), `seed_ontology.py`(`DOMAIN_GUIDE` + **표준 어휘 상수** `STANDARD_ENTITY_TYPES`/
    `STANDARD_RELATION_TYPES`/`TYPE_ALIASES`/`CANONICAL_ALIASES`/`RELATION_CONSTRAINTS`),
    `routers/projects.py`(+ `DELETE /entities`·`/relations`, `POST /query`, `POST /extract`는
    `ExtractResponse{extraction,warnings}` 래핑), `config.py`, `main.py`.
  - [v1 제거 완료(N6)] `survey.py`·`claude_enricher.py`·`routers/{survey,schema,graph}.py`·
    `cypher_builder`의 스키마-메타 함수·`neo4j_service`의 `commit_schema`/`fetch_graph`·
    `models.py`의 v1 모델(OntologySchema/NodeLabel/…)·`seed_ontology.SEED_ONTOLOGY`를 모두 삭제.
    **`seed_ontology.py`의 `DOMAIN_GUIDE`(+임계값·수질항목 상수)는 extractor가 재사용하므로 유지.**
  - 프론트(`app/frontend/src/`): `App.tsx`(브랜드 부제목 제거됨 + **N14** 헤더 우측 '온톨로지란?'
    전체화면 페이지 토글 버튼·토글 상태에 따라 content 영역을 설명 페이지로 교체), `api.ts`, `types.ts`,
    `components/{ProjectList,Workspace,ExtractionPreview,KnowledgeInventory,QueryPanel,GraphView}.tsx`.
    [N13 신규] `theme.tsx`(ThemeProvider/useTheme — data-theme·localStorage·prefers-color-scheme),
    `components/ThemeToggle.tsx`, `components/ui/{ConfirmDialog(useConfirm),Toast(useToast),Skeleton}.tsx`.
    [N14 신규] `components/OntologyGuide.tsx`(헤더 버튼이 여는 **전체화면 설명 페이지** — 그래프/온톨로지
    기초 + 팔란티어 심층 + 디지털 트윈 가설검토 + 수자원 트윈 시나리오; ConfirmDialog 접근성 패턴을
    페이지형으로 축약: onBack·Esc·트리거 포커스 복원, 참고링크 새 창. `index.css` `.guide-*` 페이지 셸.
    순수 프론트, API 과금 없음).
    `main.tsx`가 App을 **ThemeProvider>ToastProvider>ConfirmProvider**로 감싼다. `index.css`에 다크 토큰
    (`:root[data-theme="dark"]`)·글래스/notice-ink·line 토큰·모달·토스트·스켈레톤·`:focus-visible`(outline)·
    `prefers-reduced-motion`·`@media(max-width:720px)`. **GraphView 캔버스색은 CSS 토큰을 못 쓰므로 `useTheme`으로
    테마별 팔레트를 직접 고른다**(paint 콜백 인라인 유지 규약 준수).
    Workspace는 상단 **탭 2개**: **[지식설계]**=세로 스택(지식 입력 → 지식 현황 → 지식 그래프),
    **[지식활용]**=지식 탐색(`QueryPanel`). 탭 전환은 `display` 토글이라 각 탭 상태 보존. `QueryPanel`은
    자연어 질의→생성 Cypher 표시→결과 그래프(`GraphView` 재사용)+표(`KnowledgeInventory` `readOnly`
    재사용). **N12**: `QueryPanel`에 **예시 질문 프리셋 칩**(클릭 시 질문칸만 채우고 자동 실행 안 함=과금 방지,
    클릭 시 이전 결과/에러 초기화). `KnowledgeInventory`는 노드·관계 데이터 표 + 개별 삭제(`DELETE /entities`·`/relations`)
    + **10개 초과 시 클라이언트 페이지네이션** + `readOnly` prop(탐색 결과 표 재사용).
    `GraphView`(N11 강화)는 controlled·타입별 색상 + **degree 비례 노드 크기** + **오버레이 툴바**
    (노드 이름 검색→부분일치 하이라이트+나머지 디밍 / 전체 보기 `zoomToFit` / 재정렬 `d3ReheatSimulation`)
    + **정량값(N10) 노드 amber 링** + 범례 정량값 칩. paint 콜백은 **인라인 유지 필수**(콜백 identity
    변화가 정적 그래프 재드로우를 트리거 — `useCallback` 금지). auto-fit은 **새 노드 등장 시에만**
    (순수 삭제는 사용자 줌 보존). (구 `SurveyWizard`/`SchemaReview`는 이미 삭제.)
- **명령은 실제로 동작**(venv·node_modules 존재). 개발 중 백엔드(uvicorn :8000)·프론트(vite :5173)
  서버가 백그라운드로 떠 있을 수 있다. **백엔드 코드 변경 시 재시작 필요**(--reload 미사용 시 —
  포트 8000 리스너 kill 후 재기동). 프론트는 Vite HMR로 자동 반영.
- **테스트 177 passed / 27 skipped**(204 collected·실패/에러 0; 통합 27개는 opt-in —
  `RUN_NEO4J_TESTS=1`로 전부 통과. 2026-08-04 실측).
  GitHub <https://github.com/2JUNSIK/ontology.git> (main 브랜치). Windows 11 + PowerShell.

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
   **읽기 경로(text-to-cypher, N8)**: LLM이 생성한 Cypher는 신뢰하지 않는다 — **안전 3중 방어**.
   (1) `assert_read_only_cypher` 정적 검증(리터럴·주석 마스킹 후 쓰기·`CALL`·다중문 금지 +
   `$pid`(단어경계)·`_project` 필터 강제), (2) `session.execute_read`(READ access mode)로만 실행해
   쓰기 절을 **드라이버 레벨에서 거부**, (3) 결과 매핑(`_collect_graph`·`_scalarize`)이 **그래프와
   rows 모두** `_project != project_id`를 드롭 + 내부 메타(`_`프리픽스) 스크럽. 정적 검증은 보조,
   **실질 프로젝트 격리는 사후 필터**다(§4). 값은 `$pid` 하나만 바인딩(project_id 문자열 삽입 금지).
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
  `anthropic` **0.119.0**, 포트 8000. (실측 설치: fastapi 0.139.2·pydantic 2.13.4·
  pydantic-settings 2.14.2·uvicorn 0.51.0·pytest 9.1.1. `requirements.txt` floor는 이에 맞춰
  **`neo4j>=6.2,<7` / `anthropic>=0.119`** 로 고정 — 낮은 floor로 재설치 시 6.x API와 어긋나는 것 방지.)
- 프론트: **React + Vite**, 그래프 시각화 **`react-force-graph-2d`**(경량 2D 전용), 포트 5173.
  **백엔드 URL은 `api.ts`에 하드코딩**(`BASE_URL="http://localhost:8000"`, axios `timeout:120s` —
  Claude 지연 대비). `VITE_` 환경변수 미사용 → **프로덕션 배포 시 `import.meta.env.VITE_API_BASE_URL`
  등으로 환경변수화 필요**(알려진 제약). **프론트는 자동 테스트·린트 없음**(vitest/jest/testing-library/
  eslint/prettier 미설치) — 품질 게이트는 `tsc --noEmit`뿐(아래 명령 참조).
- Neo4j: 로컬 **Docker** `neo4j:5-community`(실행 시 5.26 community), `bolt://localhost:7687`,
  브라우저 7474.
- **환경변수(`config.py` — `pydantic_settings.BaseSettings`, `app/.env` 절대경로 로드·`extra=ignore`·utf-8)**:

  | 변수 | 기본값 | 비고 |
  |---|---|---|
  | `ANTHROPIC_API_KEY` | `""`(공백) | **필수**·백엔드 전용(프론트 노출 금지). 없으면 추출/탐색은 빈 결과로 우아한 열화 |
  | `ANTHROPIC_MODEL` | `claude-opus-4-8` | 변경 시 §불변식 5 참조 |
  | `NEO4J_URI` | `bolt://localhost:7687` | 로컬 Docker |
  | `NEO4J_USER` | `neo4j` | |
  | `NEO4J_PASSWORD` | `ontology_dev_pw` | dev 기본값 — **운영에서 변경 필수**(docker-compose `NEO4J_AUTH`도 이 값 사용) |

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
& "app\backend\.venv\Scripts\python.exe" -m pytest app\backend      # 177 passed / 27 skipped
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

### API 엔드포인트 (요약 — 상세·요청/응답은 PLAN.md §5)

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/api/projects` | 프로젝트 목록 |
| POST | `/api/projects` | 프로젝트 생성 |
| DELETE | `/api/projects/{id}` | 프로젝트 삭제 |
| POST | `/api/projects/{id}/extract` | 자연어→추출 미리보기(**Claude 호출·과금**) → `ExtractResponse{extraction,warnings}` |
| POST | `/api/projects/{id}/ingest` | 편집본 MERGE 반영 → `{stats,graph}` |
| GET | `/api/projects/{id}/graph` | 프로젝트 그래프 `{nodes,links}` |
| DELETE | `/api/projects/{id}/entities` | 노드+연결관계 삭제 → `{stats,graph}` |
| DELETE | `/api/projects/{id}/relations` | 관계만 삭제 → `{stats,graph}` |
| POST | `/api/projects/{id}/query` | 자연어 탐색(text-to-cypher, **Claude 호출·과금**, 읽기 전용) |

### 테스트 커버리지 맵 (`app/backend/tests/`)

| 테스트 파일 | 커버 대상 |
|---|---|
| `test_models.py` | Entity/Relation/Extraction 검증·식별자 방어선·정량 속성 |
| `test_kg_cypher_builder.py` | ingest/관계 MERGE 생성·순수성·인젝션·타입 그룹핑 |
| `test_claude_extractor.py` | Claude 추출 흐름·구조화 출력·실패 열화(모킹) |
| `test_text_to_cypher.py` | 자연어→읽기 Cypher 생성·실패 처리(모킹) |
| `test_ontology_normalizer.py` | 별칭·타입 표준화·병합·domain/range 경고 |
| `test_seed_ontology.py` | 도메인 상수·임계값·별칭 일관성 |
| `test_neo4j_read_mapping.py` | 읽기 결과 매핑·프로젝트 사후 격리·메타 스크럽 |
| `test_projects_api.py` | FastAPI 엔드포인트·요청 모델 정제 |
| `test_kg_integration.py` | 실 Neo4j CRUD/ingest/query 왕복 (**27개·opt-in**, `RUN_NEO4J_TESTS=1`) |

### 로깅 · 에러 처리

- 각 모듈이 `logging.getLogger(__name__)` 사용(`neo4j_service`·`claude_extractor`·`text_to_cypher`·
  `routers/projects`). `main.py`에 `logging.basicConfig`/전역 설정 **없음** → Python 표준 기본
  (StreamHandler·WARNING 이상)만 나온다. 프로덕션에선 uvicorn 로그 설정 또는 `basicConfig` 권장.
- 주요 예외 흐름:
  - Neo4j 미가동/연결 불가 → `ServiceUnavailable`을 잡아 `Neo4jUnavailable`로 승격 → 라우터가 **HTTP 503**.
  - 프로젝트 없음 → **HTTP 404**.
  - Claude 실패/키 없음/빈 입력 → 빈 `Extraction` 반환(**우아한 열화**, 사용자는 수동 입력 지속).
  - 읽기 경로(`/query`)의 변환 실패·`assert_read_only_cypher` 검증 실패·Cypher 문법/실행 오류는
    **HTTP 200 + `error` 필드**로 우아하게 열화(재질문 유도 — HTTP 에러로 던지지 않음. `routers/projects.py`
    `post_query`, `QueryResponse.error`). 연결 불가만 여기서도 503.
  - 값/식별자 방어선 위반 → Pydantic `ValidationError`(추출 재검증에선 해당 항목만 드롭).

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
- **`app/docker-compose.yml` 실제 스펙**: 프로젝트명 `ontology-builder`, 컨테이너명 `ontology-neo4j`,
  볼륨 `ontology_neo4j_data`(→`/data`)·`ontology_neo4j_logs`(→`/logs`), `restart: unless-stopped`,
  healthcheck는 번들 `cypher-shell`로 Bolt 접속 확인(interval 10s·timeout 5s·retries 12·start_period 30s).
  `NEO4J_AUTH`는 `.env`의 `NEO4J_PASSWORD`(없으면 `ontology_dev_pw`)를 사용 → **최초 기동 시의 계정이
  볼륨에 고정되므로, 비밀번호를 바꾸려면 `docker compose down -v`로 볼륨을 초기화한 뒤 재기동**할 것.
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
