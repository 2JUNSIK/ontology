# 지식그래프 빌더 (Knowledge Graph Builder) — MVP 구현 계획 (v2)

> **v2 피벗(2026-07-24)**: 기존 "구조화 설문 마법사" 방향을 폐기하고, **자연어 지식 입력형
> 지식그래프 빌더**로 전환했다. 직원이 문장으로 지식을 입력하면 Claude가 엔티티(노드)와
> 관계를 추출해 **프로젝트별 지식그래프에 누적**한다. (v1 설문/스키마 흐름은 §부록 참조.)

## Context (배경)

K-water 수자원 도메인(특히 **녹조 관리 / 수질오염 대응**) 지식을 가진 직원이, 온톨로지
이론을 몰라도 **자연어로 지식을 한 문장씩 입력**하면, 앱이 그 문장에서 노드·관계를 뽑아
지금까지 쌓인 지식그래프에 자동으로 더해 주는 웹앱.

예) 프로젝트 "녹조 대응":
- "녹조는 남조류가 과도하게 증식해 물이 녹색으로 변하는 현상이다."
  → `(녹조:현상)`, `(남조류:생물)`, `(녹조)-[원인]->(남조류)`
- "조류경보제는 관심·경계·대발생 3단계로 운영된다."
  → `(조류경보제:제도)`,`(관심:경보단계)`… `(조류경보제)-[단계]->(관심)`…
- "관심 단계는 남조류세포수가 1000 cells/mL 이상일 때 발령된다."
  → `(남조류세포수:지표)` 신규, `(관심)-[기준지표]->(남조류세포수)`; 이미 있는 `관심`은 재사용.

**해결 문제**: 온톨로지/그래프 모델링은 전문 기술인데 도메인 지식은 현장 직원에게 있다.
이 간극을 "자연어 입력 + LLM 추출 + 미리보기 확인"으로 메운다.

**소스 관리**: GitHub <https://github.com/2JUNSIK/ontology.git> (main). Windows 11 + PowerShell.

## 확정된 결정 (v2)

- **인터페이스**: 구조화 설문 **폐기** → **자유 자연어 지식 입력**.
- **흐름**: 입력 → Claude 추출 → **미리보기/편집 → 확인 시 그래프 병합(MERGE)**. (자동반영 아님.)
- **프로젝트**: 여러 프로젝트 **생성/전환/삭제**, 각 프로젝트가 독립 지식그래프.
- **스택**: 백엔드 Python 3.14 + FastAPI, `neo4j` 6.2.0, `anthropic` 0.119.0(모델 `claude-opus-4-8`),
  프론트 React + Vite + `react-force-graph-2d`. Neo4j 로컬 Docker `neo4j:5-community`(bolt 7687).
  (`requirements.txt` floor는 실측 설치에 맞춰 `neo4j>=6.2,<7`·`anthropic>=0.119`로 고정.)
- **재사용**: `neo4j_service`(드라이버/실행), `cypher_builder.escape_identifier`(인젝션 방어),
  Claude 구조화 출력 패턴, `GraphView`, `models`의 식별자 방어선(`_clean_identifier` 등).

## 진행 현황 (2026-08-05 기준)

**완료: N1~N14** (백엔드 v2 + 프론트 재작성 + 구 v1 코드 완전 제거 + 지식 현황 데이터 관리 +
**자연어 그래프 탐색(text-to-cypher, 읽기 경로)** + **표준 어휘 정규화(N9)** + **정량 속성 구조화(N10)** +
**그래프 시각화 강화(N11)** + **탐색 예시 질문 프리셋(N12)**). end-to-end 동작 확인. 앱이 이제 입력(쓰기)뿐
아니라 **자연어 질의로 탐색(읽기)** 까지 하는 양방향이 됐고, "실무형 지식그래프 강화"로 **① 표준 타입/관계 어휘
+ 별칭→표준명 정규화(중복 방지)** **② 정량 속성(value/unit/comparator/observed_at을 노드 속성으로 — 임계값·대표
수치)** 을 갖췄다. UI는 상단 **지식설계/지식활용 2개 탭**으로 입력·관리와 탐색을 분리했고(상단 브랜드 부제목 제거),
**N11**에서 그래프 시각화를 강화(degree 비례 노드 크기·노드 검색/하이라이트·전체보기/재정렬·정량값 amber 링),
**N12**에서 지식활용 탐색에 **예시 질문 프리셋**(클릭 시 질문칸만 채움·자동 실행 안 함)을 더해 첫 사용자
진입장벽을 낮췄다. **N13**에서 **디자인/UX 리프레시**(다크모드 토글·커스텀 확인 모달·토스트 알림·스켈레톤
로딩·빈 상태 CTA·비용 배지·반응형·접근성[focus-visible·aria·inert·prefers-reduced-motion])를 추가해
현재 Toss 톤을 유지·정제하면서 데모/현업 환경 다양성에 대응했다(순수 프론트, API 과금 없음).
**N14**에서 **온톨로지 설명자료(헤더 '온톨로지란?' → 앱 내 전체화면 페이지)**를 추가했다 — 교재의
그래프DB·온톨로지 강의에 **팔란티어 온톨로지·디지털 트윈** 공개자료(공식 docs/blog로 검증)를 더해 이 앱
맥락(녹조/수질 예시 위주)으로 쉽게 재구성한 직원 교육자료. 신규 `components/OntologyGuide.tsx`(모달→전체
화면 페이지 전환), `App.tsx` 헤더 페이지 토글, `index.css` 페이지 셸. 내용: 그래프/온톨로지 기초 → 팔란티어
심층(의사결정 모델·semantic+kinetic·RAG→OAG·해자) → 디지털 트윈 가설 검토(관계기반 추론이 핵심 + 실시간
상태·행동 보강) → 수자원 트윈 확장 시나리오(대청호 녹조). 순수 프론트·과금 없음·tsc/build 통과.
**다음: 프론트 디자인/기능 확장 계속.**

> **git 상태(2026-08-05)**: **N1~N14 전부 main에 머지·push 완료**(`main`=`origin/main`=`809cf07`).
> N14(온톨로지 설명 페이지)를 `feat-ontology-guide`에서 ff 머지한 뒤 그 피처 브랜치를 **로컬·원격 모두 삭제**. **현재 브랜치는 `main` 하나뿐.**
> `gh` 미설치 → 다음 작업은 새 피처 브랜치에서 하고 PR은 push 후 반환된 웹 링크로 연다. (참조: 메모리 `git-feature-branch-workflow`)

- **백엔드**: `models.py`(Entity/Relation/Extraction + `_clean_value`/`_clean_label_or_type`),
  `cypher_builder.py`(`build_entity_constraint`/`build_ingest_statements`, `ENTITY_BASE_LABEL`),
  `neo4j_service.py`(프로젝트 CRUD·`ingest`·`fetch_project_graph`·`delete_entity`·`delete_relation`),
  `claude_extractor.py`, `routers/projects.py`(projects/extract/ingest/graph + DELETE
  entities/relations). `main.py`에 projects 라우터 등록.
- **프론트**: `App.tsx`(프로젝트 목록↔작업공간), `ProjectList`, `Workspace`(**세로 스택**:
  지식 입력→지식 현황→지식 그래프 오케스트레이션), `ExtractionPreview`(편집/선택 후 ingest),
  `KnowledgeInventory`(노드·관계 데이터 표 + 개별 삭제 + 10개/페이지 페이지네이션), `GraphView`
  (controlled, 타입별 색상). 구 `SurveyWizard`/`SchemaReview`는 삭제.
- **테스트**: 177 passed / 27 skipped(204 collected·실패/에러 0, 통합 opt-in). 통합 27개는 실
  Neo4j(`RUN_NEO4J_TESTS=1`)로 별도 전부 통과. 프론트 `tsc --noEmit` 0 에러. (2026-08-04 실측)
- **적대적 검수 완료**(백엔드·프론트 각각): 백엔드 **must-fix 없음**(인젝션·원자성·프로젝트
  격리·503·모델 재검증 라이브 통과) + LOW 3건 반영(관계 중복 제거·stub 설명 `''` 정규화·
  ingest 시 제약 방어). 프론트 must-fix 반영(제외 노드를 참조하는 관계 유령화 방지, 삭제
  로딩상태, ingest 통계 표시, 미리보기 이탈 경고).
- **구 v1(설문/스키마) 백엔드 제거 완료**(N6): `survey.py`, `routers/{survey,schema,graph}.py`,
  `claude_enricher.py`, `seed_ontology.SEED_ONTOLOGY`, `models.py`의 v1 모델(OntologySchema/
  NodeLabel/…), `cypher_builder`의 스키마-메타 함수, `neo4j_service`의 `commit_schema`/`fetch_graph`,
  대응 테스트를 모두 삭제. `DOMAIN_GUIDE`(+상수)와 공유 인젝션 방어선은 유지. 방어선 테스트는
  v2 Entity/Relation 기준으로 재작성해 커버리지 보존.
- **지식 현황(데이터 관리) 완료**(N7): `DELETE /api/projects/{id}/entities`(노드+연결관계
  DETACH)·`/relations`(관계만) 추가 — 값은 파라미터 바인딩, 관계타입은 `type(r)=$rtype` 값비교로
  인젝션 안전, 삭제 요청모델은 ingest와 동일 정제(NFC+trim)해 '조용한 무삭제' 방지. 프론트는
  좌우 2컬럼→**세로 스택** 재구성, `KnowledgeInventory` 표에서 개별 삭제(0건 안내 포함) + 10개
  초과 시 클라이언트 페이지네이션. 적대적 검수 must-fix 없음(인젝션·프로젝트 격리·프론트 뮤테이션
  안전, SHOULD/LOW 반영).

## 1. 아키텍처 & 데이터 흐름

```
[React 프론트]                         [FastAPI 백엔드]                      [외부]
 ProjectList  ──생성/선택──▶  /api/projects (CRUD) ─────────────▶ Neo4j (:_Project)
 Workspace:
   지식입력창 ──텍스트──▶ /api/projects/{id}/extract ─▶ claude_extractor ─▶ Anthropic API
   미리보기  ◀──Extraction(entities,relations)─┘
   (편집/확인) ──확정──▶ /api/projects/{id}/ingest ─▶ cypher_builder(MERGE) ─▶ Neo4j (:_Entity)
   GraphView ◀──{nodes,links}── /api/projects/{id}/graph ◀──────────────────── Neo4j
```

핵심 루프: **입력 → 추출(미리보기) → 확인/편집 → 병합(누적) → 반복.**

## 2. 데이터 모델 (Neo4j)

- **프로젝트**: `(:_Project {id, name, description, created_ts})`. `id`는 uuid4 hex.
- **엔티티(지식 노드)**: `(:_Entity {_project, _name, description})` + **동적 타입 라벨**
  (예: `:현상`, `:생물`, `:제도`, `:경보단계`, `:지표`). 정체성 = **(`_project`,`_name`) 복합
  UNIQUE 제약** → 같은 이름 재입력 시 자동 병합(MERGE).
- **관계**: `(:_Entity)-[:동적관계타입 {description}]->(:_Entity)`, 양 끝이 같은 프로젝트.
- 프로젝트 삭제 시 그 프로젝트의 `:_Entity`와 `:_Project`를 함께 정리.

## 3. 공통 중간표현 (models.py, Single Source of Truth)

기존 식별자 방어선(`_clean_identifier`, `_clean_label_or_type`) 위에 KG 표현을 추가:

```python
class Entity(BaseModel):
    name: str            # 값(파라미터 바인딩) — 길이 제한, 제어문자 거부
    type: str = ""       # 타입 라벨(식별자) — 비면 미분류. 비지 않으면 _clean_label_or_type 검증
    description: str = ""
    # 정량 속성(N10, 전부 optional·값·하위호환). 임계값·대표 수치를 노드 속성으로.
    value: float | None = None   # NaN/Inf/bool 거부. value 없으면 comparator/unit은 정규화로 드롭
    unit: str = ""               # 단위(값) 예: cells/mL
    comparator: str = ""         # 화이트리스트: "", ">=", "<=", ">", "<", "="
    observed_at: str = ""        # 시각(값, ISO8601 문자열)

class Relation(BaseModel):
    source: str; target: str   # 값(엔티티 이름)
    type: str                  # 관계타입(식별자) — _clean_label_or_type 검증
    description: str = ""

class Extraction(BaseModel):   # Claude 추출 결과(미리보기/ingest 공용)
    entities: list[Entity]
    relations: list[Relation]
    summary: str = ""
```

- **이름/설명은 값** → Cypher에 파라미터로만(`$param`). **타입 라벨/관계타입은 식별자** →
  화이트리스트(`_clean_label_or_type`, 백틱/제어/‘_’프리픽스 거부) + 백틱 이스케이프.
- 프론트 `types.ts`는 이 모델과 1:1 대응.

## 4. Claude 추출 (claude_extractor.py)

- 입력: 프로젝트의 지식 문장(+선택적으로 기존 타입/엔티티 힌트로 일관성 유도).
- 출력(구조화 강제): `{entities, relations, summary}`. free-form dict 회피 위해 전용 출력 스키마로
  받고 내부 `Extraction`으로 **재검증**(식별자 방어선 통과, 실패분은 드롭/경고).
- **prompt caching**: 안정 프리픽스(시스템 지침 + 도메인 가이드 `DOMAIN_GUIDE`)에 `cache_control`.
- **우아한 열화**: 키 없음/실패 시 빈 `Extraction` → 사용자는 수동 입력으로 계속 가능.
- **비용**: `/extract`가 매 호출 실제 Claude를 부른다(과금). 프론트에 고지.

## 5. FastAPI 엔드포인트

| 메서드 | 경로 | 요청 | 응답 |
|---|---|---|---|
| GET | `/api/projects` | – | 프로젝트 목록 |
| POST | `/api/projects` | `{name, description}` | 생성된 프로젝트 |
| DELETE | `/api/projects/{id}` | – | `{deleted}` |
| POST | `/api/projects/{id}/extract` | `{text}` | `Extraction`(미리보기, Claude 호출) |
| POST | `/api/projects/{id}/ingest` | `Extraction`(편집본) | `{stats, graph}` |
| GET | `/api/projects/{id}/graph` | – | `{nodes, links}` |
| DELETE | `/api/projects/{id}/entities` | `{name}` | `{stats, graph}` (노드+연결관계 삭제) |
| DELETE | `/api/projects/{id}/relations` | `{source, target, type}` | `{stats, graph}` (관계만 삭제) |
| POST | `/api/projects/{id}/query` | `{question}` | `{cypher, explanation, graph, rows, columns, error}` (자연어 탐색, Claude 호출) |

삭제 값(이름·관계타입)은 ingest와 동일하게 정제(NFC+trim, `_clean_value`/`_clean_label_or_type`)해
저장된 `_name`과 매칭한다. 관계타입은 `type(r)=$rtype` 값 비교 → 동적 식별자 미삽입(인젝션 안전).

## 6. Neo4j 반영 (cypher_builder + neo4j_service)

- **인젝션 방지(불변식 §3)**: 타입 라벨/관계타입은 `escape_identifier`(재검증+백틱), 값은
  파라미터. 동적 라벨/관계타입은 **타입별로 그룹핑**해 문 하나당 하나의 (검증된) 식별자만
  삽입한다(라벨은 UNWIND로 파라미터화 불가하므로).
- **엔티티 MERGE**: `MERGE (n:_Entity {_project:$pid,_name:row.name})` 후 타입별 `SET n:` + 라벨.
- **관계 MERGE**: 끝점 엔티티를 먼저 보장(관계 endpoint 중 노드 없는 것은 미분류 stub로 보강)
  → `MATCH … MERGE (a)-[:관계타입]->(b)`.
- **원자성**: ingest의 데이터 연산(엔티티/라벨/관계)은 **하나의 관리형 쓰기 트랜잭션**으로
  묶는다. 스키마 DDL(제약)은 별도 auto-commit(스키마/데이터 혼용 금지 회피).
- `cypher_builder`는 **순수 함수**(부수효과 없음, 단위테스트 대상).

## 7. 프론트 화면 (ProjectList → Workspace)

- **상단바(topbar)** — 브랜드 + **'온톨로지란?'**(N14, 클릭 시 content 영역을 **전체화면 온톨로지 설명
  페이지**로 토글) + 테마 토글(N13). 설명 페이지는 돌아가기/Esc로 닫고 트리거 버튼으로 포커스 복원.

1. **ProjectList** — 프로젝트 목록/생성/선택/삭제.
2. **Workspace** — 상단 **탭 2개**(지식설계 / 지식활용). 탭 전환은 `display` 토글이라 각 탭 상태를
   보존한다(탐색 결과가 탭 이동으로 사라지지 않음).
   - **[지식설계]** — 세로 스택(전체 폭): (a) **지식 입력** — 입력창 + "추출"(비용 경고) + 미리보기
     패널(`ExtractionPreview`: 엔티티/관계 체크·편집·삭제 → "그래프에 추가"); (b) **지식 현황**
     (`KnowledgeInventory`: 노드·관계 표 + 행별 개별 삭제 + 10개/페이지 페이지네이션);
     (c) **지식 그래프**(`GraphView`: 누적 시각화, 노드 클릭 시 속성/타입 패널).
   - **[지식활용]** — **지식 탐색**(`QueryPanel`): 자연어 질문 → 생성 Cypher 표시(투명성) →
     결과 그래프(`GraphView` 재사용) + 표(`KnowledgeInventory` `readOnly` 재사용). 읽기 전용.

## 8. 도메인 가이드 (seed_ontology.py 재활용)

녹조/수질 임계값·개념을 Claude **추출 프롬프트의 도메인 가이드**로 사용. 타입 라벨 예시:
`현상·생물·제도·경보단계·지표·오염원·대응조치·기관·저수지·측정소`. 조류경보제 임계값(남조류
세포수): 관심 ≥1,000 / 경계 ≥10,000 / 대발생 ≥1,000,000 cells/mL.

## 9. 로컬 실행 (PowerShell)

```powershell
cd app; docker compose up -d                       # Neo4j (이미 캐시된 이미지)
cd backend; .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000          # http://localhost:8000/docs
cd ..\frontend; npm install; npm run dev           # http://localhost:5173
```
테스트: `& "app\backend\.venv\Scripts\python.exe" -m pytest app\backend`
(Neo4j 통합 테스트는 `$env:RUN_NEO4J_TESTS=1`로 opt-in.)

## 10. 마일스톤 (v2)

- **[x] N1** `models.py`(Entity/Relation/Extraction) + `cypher_builder`(엔티티/관계 MERGE,
  프로젝트 제약, 타입 그룹핑) + 단위테스트(인젝션·순수성).
- **[x] N2** `neo4j_service`(프로젝트 CRUD, `ingest`, `fetch_project_graph`) + 통합테스트(opt-in).
- **[x] N3** `claude_extractor.py`(구조화 출력 + 재검증 + 캐시 + 우아한 열화).
- **[x] N4** `routers/projects.py`(projects/extract/ingest/graph) + `main.py` 등록.
- **[x] N5** 프론트 재작성(ProjectList + Workspace + 미리보기 + 누적 GraphView).
- **[x] N6** 구 코드 정리(v1 설문/스키마 라우터·`survey.py`·`claude_enricher.py`·스키마-메타
  cypher/서비스·v1 모델·구 테스트 제거) + 다듬기 → 커밋. 방어선 테스트는 v2 모델 기준 재작성.
- **[x] N7** 지식 현황(데이터 관리) — 노드·관계 표 + 개별 삭제(`delete_entity`/`delete_relation`,
  `DELETE /entities`·`/relations`, 인젝션 안전) + 좌우→세로 레이아웃 재구성 + 클라이언트
  페이지네이션(10개/페이지). 통합/검증 테스트 추가, 적대적 검수 통과.
- **[x] N8** 자연어 그래프 탐색(**text-to-cypher, 읽기 경로**) — `text_to_cypher.generate_query`
  (자연어→읽기전용 Cypher, 구조화 출력 + 캐시 + 우아한 열화), `cypher_builder.assert_read_only_cypher`
  (정적 안전 검증: 리터럴/주석 마스킹 + 쓰기·CALL 금지 + `$pid`/`_project` 필터 강제),
  `neo4j_service.run_read_query`(READ 트랜잭션 실행 + 결과 매핑 `_collect_graph`/`_scalarize` —
  **그래프·rows 모두 프로젝트 사후 필터 + 내부 메타 스크럽**), `POST /query` 라우터,
  프론트 `QueryPanel`(생성 Cypher 표시 + 결과 그래프 + 표) + `KnowledgeInventory` readOnly 재사용.
  **안전 3중 방어**(정적 검증 → READ access mode 쓰기 거부 → 결과 사후 격리 필터). 단위/통합/검증
  테스트 추가, 적대적 검수 후 must-fix 2건(rows 격리 유출·`$pid` substring 우회) 반영.
- **[x] N9** 표준 어휘 정규화(스키마 + 엔티티 별칭) — `seed_ontology`에 `STANDARD_ENTITY_TYPES`/
  `STANDARD_RELATION_TYPES`/`TYPE_ALIASES`/`CANONICAL_ALIASES`/`RELATION_CONSTRAINTS` 상수 + `DOMAIN_GUIDE`
  주입, 신규 순수 함수 `ontology_normalizer.py`(`canonicalize_extraction`: 별칭·타입 표준화 + 관계 끝점
  치환 + 이름/관계 dedup 병합 + 방어선 재통과 / `validate_domain_range`: 위반을 **경고로만**, 삭제 안 함),
  `claude_extractor._to_internal` 후처리, `POST /extract`를 `ExtractResponse{extraction,warnings}`로 래핑,
  프론트 미리보기 경고 배너 + 표준 타입 datalist. 검수 반영(경고 라벨 canonical화, 타입충돌 병합 정책 명시).
- **[x] N10** 정량 속성·단위 구조화(실무형, 노드 속성 방식) — `models.Entity`에 optional
  `value/unit/comparator/observed_at`(comparator 화이트리스트, value NaN/Inf/bool 거부, 고아 정량 정규화),
  `cypher_builder`가 정량 속성을 **파라미터로만** SET(value는 `IS NOT NULL` 시 갱신·아니면 유지, sticky),
  `neo4j_service.fetch_project_graph`/`_node_payload` RETURN 확장, `DOMAIN_GUIDE` 모델링 원칙을 '정량 속성
  기록'으로 갱신, 프론트 미리보기 정량 입력·지식현황 값 컬럼·그래프 패널 표시(`formatQuantity`).
  검수 반영(고아 정량 정규화 MED-1, sticky 정책 명문화 MED-2). *측정 이벤트 노드/시계열은 범위 밖(후속).*
- **[x] N11** 그래프 시각화 강화(순수 프론트, `GraphView.tsx`) — degree(연결 수) 비례 노드 크기(sqrt·상한13),
  오버레이 툴바(노드 이름 검색→부분일치 하이라이트+나머지 디밍 / 전체 보기 `zoomToFit` / 재정렬 `d3ReheatSimulation`),
  정량 속성(N10) 노드에 amber 링 + 범례 정량값 칩(패널 안 열어도 인지). 적대적 검수 반영: S2(새 노드 등장 시에만
  auto-fit → 순수 삭제는 사용자 줌/뷰 보존), S1(refit 리셋=data 기준), S3(엔진 정지 전 전체보기 비활성),
  N1(paint 콜백 인라인 유지 주석=정적 그래프 재드로우 보호), N2/N4/N6. **API 과금 없음.** `tsc --noEmit` 통과.
- **[x] N12** 탐색 UX 예시 질문 프리셋(순수 프론트, `QueryPanel.tsx`) — 그래프형·표(집계)형·정량값(N10)을
  고루 커버하는 예시 질문 칩 5개. 클릭 시 질문칸만 **채우고 자동 실행 안 함**(`/query`는 Claude 과금이라 실행은
  명시적 사용자 액션으로 유지) + **이전 결과/에러 초기화**(질문·화면 결과 불일치 방지) + 로딩 중 비활성 +
  접근성 `role=group`/`aria-labelledby`. 적대적 검수 must-fix 없음(자동 제출 경로 없음 확인, SHOULD·NICE 반영).
  **API 과금 없음.** `tsc --noEmit` 통과.
- **[x] N13** 디자인/UX 리프레시(순수 프론트, 다크모드까지 풀 리프레시·현재 Toss 톤 유지·정제) —
  **테마화**: `index.css`에 `:root[data-theme="dark"]` 토큰 오버라이드 + 글래스/notice-ink·line 토큰
  (컴포넌트 무수정 전환), **신규 프리미티브** `theme.tsx`(ThemeProvider/useTheme·localStorage·prefers-color-scheme),
  `components/ThemeToggle.tsx`, `components/ui/{ConfirmDialog(useConfirm, promise 기반·focus trap·Esc·배경 inert),
  Toast(useToast·자동소멸·error=assertive), Skeleton}`. **UX**: `window.confirm`(4곳)→커스텀 모달, 생성/반영/삭제
  성공→토스트, 로딩→스켈레톤, 빈 상태 CTA, 추출·탐색 버튼 비용 배지. **GraphView 다크 캔버스**(하드코딩색→`useTheme`
  팔레트, 다크 전용 노드 팔레트, paint 콜백 인라인 유지=N11 규약, Esc로 패널 닫기). **반응형**(≤720px)·**접근성**
  (focus-visible outline=clip-proof, aria-modal/describedby, prefers-reduced-motion). 적대적 검수 2회(정확성·a11y)
  후 must-fix 반영: useConfirm 이중오픈/언마운트 promise 유실, 토스트 pointer-events, primary 버튼/다크 muted 대비,
  disabled 가독성, 캔버스 저대비 노드색. **API 과금 없음.** `tsc --noEmit` 0에러.
- **[x] N14** 온톨로지 설명자료(순수 프론트, `components/OntologyGuide.tsx` + `App.tsx` 헤더 + `index.css`) —
  헤더 우측 '온톨로지란?' 버튼이 여는 **앱 내 전체화면 설명 페이지**. 교재(그래프DB→지식그래프→온톨로지→
  GraphRAG)에 **팔란티어 온톨로지·디지털 트윈** 공개자료(공식 docs/blog 검증)를 더해 직원용으로 재구성.
  내용: ① 그래프/프로퍼티그래프/온톨로지 기초·공리와 추론 → ② **팔란티어 심층**(온톨로지=의사결정 모델,
  semantic 명사 + kinetic 동사, RAG→OAG, Disruption Bot, 재사용·전환비용 해자) → ③ **디지털 트윈 가설
  검토**('물리세계 이해 + 관계기반 추론'을 맞다고 확인하되 실시간 상태·행동 보강) → ④ **수자원 트윈 확장
  시나리오**(대청호 녹조: 센서→경계 판정→하류 영향 식별→대응조치 승인·실행→피드백). 처음 모달로 만들었다가
  콘텐츠가 많아 **전체화면 페이지로 전환**(createPortal/inert/focus-trap 제거, onBack/Esc/트리거 포커스 복원,
  헤더 토글 aria-pressed, 참고링크 새 창). 적대적 검수 2회(a11y·**사실검증**) must-fix 없음 + SHOULD 반영
  (토글 aria-label 상태화·포커스 복원·인용처럼 보이던 예시를 저자해설로 전환·2차자료 표현 완화). **API 과금
  없음.** tsc/build 통과. *(main 머지 완료 · 2026-08-05)*

각 마일스톤: 코드 → 적대적 서브에이전트 검수 + 엣지케이스 테스트 → must-fix 반영 → 커밋.

## 검증 (Verification)

1. Neo4j 기동 → 프로젝트 생성 → 지식 문장 입력 → 추출 미리보기 확인 → "그래프에 추가" →
   GraphView에 노드·관계 누적 → 같은 엔티티 재입력 시 중복 없이 병합되는지.
2. Neo4j 브라우저(7474): `MATCH (n:_Entity {_project:'<id>'}) RETURN n`.
3. 단위테스트: cypher_builder(엔티티/관계 MERGE 생성·인젝션), 통합(ingest→graph 왕복·병합 멱등).

## 부록 A. v1(폐기)에서 재사용/제거

- **재사용**: `neo4j_service` 드라이버·실행·503 열화, `cypher_builder.escape_identifier`·
  `CypherStatement`, `models`의 식별자 방어선, `GraphView`, `seed_ontology.DOMAIN_GUIDE`.
- **제거(N6)**: `survey.py`, `routers/survey.py`, `/api/suggest`·`/api/schema*`(위저드),
  `claude_enricher.py`(→ `claude_extractor`로 대체), 관련 테스트 및 구 프론트 컴포넌트.

## MVP 이후 확장

사용자 인증/권한, 그래프 버전/이력, 추출 규칙 튜닝, 엔티티 병합/별칭 관리, 대량 문서 일괄
적재, 파생 온톨로지(타입·관계타입 집합) export, 프롬프트 캐시 pre-warm.
