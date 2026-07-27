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
- **스택**: 백엔드 Python 3.14 + FastAPI, `neo4j` 6.2, `anthropic` 0.119(모델 `claude-opus-4-8`),
  프론트 React + Vite + `react-force-graph-2d`. Neo4j 로컬 Docker `neo4j:5-community`(bolt 7687).
- **재사용**: `neo4j_service`(드라이버/실행), `cypher_builder.escape_identifier`(인젝션 방어),
  Claude 구조화 출력 패턴, `GraphView`, `models`의 식별자 방어선(`_clean_identifier` 등).

## 진행 현황 (2026-07-27 기준)

**완료: N1~N7** (백엔드 v2 + 프론트 재작성 + 구 v1 코드 완전 제거 + 지식 현황 데이터 관리).
end-to-end 동작 확인. **다음: 프론트 디자인/기능 확장 계속.**

> **git 상태**: N6·N7은 각각 피처 브랜치에 있고 **아직 main 미머지**다. `main`=origin/main(구
> 상태), `n6-cleanup`(N6 커밋), `feat-knowledge-inventory`(N7 = 지식 현황+세로 레이아웃+삭제+
> 페이지네이션, n6-cleanup 위에 스택). `gh` 미설치 → PR은 push 후 반환된 웹 링크로 연다. 권장
> 머지 순서: n6-cleanup → feat-knowledge-inventory.

- **백엔드**: `models.py`(Entity/Relation/Extraction + `_clean_value`/`_clean_label_or_type`),
  `cypher_builder.py`(`build_entity_constraint`/`build_ingest_statements`, `ENTITY_BASE_LABEL`),
  `neo4j_service.py`(프로젝트 CRUD·`ingest`·`fetch_project_graph`·`delete_entity`·`delete_relation`),
  `claude_extractor.py`, `routers/projects.py`(projects/extract/ingest/graph + DELETE
  entities/relations). `main.py`에 projects 라우터 등록.
- **프론트**: `App.tsx`(프로젝트 목록↔작업공간), `ProjectList`, `Workspace`(**세로 스택**:
  지식 입력→지식 현황→지식 그래프 오케스트레이션), `ExtractionPreview`(편집/선택 후 ingest),
  `KnowledgeInventory`(노드·관계 데이터 표 + 개별 삭제 + 10개/페이지 페이지네이션), `GraphView`
  (controlled, 타입별 색상). 구 `SurveyWizard`/`SchemaReview`는 삭제.
- **테스트**: 72 passed / 15 skipped(통합 opt-in). 통합 15개는 실 Neo4j(`RUN_NEO4J_TESTS=1`)로
  별도 전부 통과. 프론트 `tsc --noEmit` 0 에러.
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

## 7. 프론트 화면 (2뷰)

1. **ProjectList** — 프로젝트 목록/생성/선택/삭제.
2. **Workspace** — **세로 스택**(전체 폭, 같은 너비):
   - (a) **지식 입력** — 입력창 + "추출" 버튼(비용 경고) + 추출 **미리보기 패널**
     (`ExtractionPreview`: 엔티티/관계 체크·편집·삭제 → "그래프에 추가").
   - (b) **지식 현황**(`KnowledgeInventory`) — 노드·관계를 **데이터 표**로 관리, 행별 **개별 삭제**
     (노드 삭제 시 연결 관계도 함께 제거 — 확인 다이얼로그). 삭제 결과(0건 포함) 안내.
   - (c) **지식 그래프**(`GraphView`, 항상 표시) — 노드 클릭 시 속성/타입 패널.

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
