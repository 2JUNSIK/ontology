# Ontology Builder — app

K-water 녹조/수질 도메인 **자연어 지식그래프 빌더**(v2) 웹앱. 직원이 문장으로 지식을 입력하면
Claude가 엔티티·관계를 추출해 프로젝트별 지식그래프에 MERGE 누적하고, 자연어 질의로 탐색까지 한다.
전체 설계는 상위 폴더의 [`../PLAN.md`](../PLAN.md), 작업 규약은 [`../CLAUDE.md`](../CLAUDE.md) 참조.

```
app/
├─ docker-compose.yml   # Neo4j 5 (community) — 7474(browser) / 7687(bolt)
├─ .env.example         # 복사해서 .env 작성
├─ backend/             # FastAPI (Python)
└─ frontend/            # React + Vite
```

## 사전 준비

- Docker Desktop (설치됨, AutoStart 꺼져 있으면 먼저 실행)
- Python 3.14
- Node.js 18+

## 실행 (PowerShell)

```powershell
# 0) Docker Desktop이 꺼져 있으면 먼저 기동
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# 1) 환경변수 준비
Copy-Item .env.example .env      # 이후 .env 안의 ANTHROPIC_API_KEY 채우기 (추출/탐색에 필요)

# 2) Neo4j 기동 (neo4j:5-community 이미지 캐시됨 → 즉시 기동)
docker compose up -d
#    Neo4j Browser: http://localhost:7474  (user: neo4j / pw: .env의 NEO4J_PASSWORD)

# 3) 백엔드 (venv 이미 존재)
cd backend
.\.venv\Scripts\Activate.ps1
#    최초 세팅이라면: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # http://localhost:8000/health, /docs

# 4) 프론트
cd ..\frontend
npm install
npm run dev                                  # http://localhost:5173
```

## Neo4j 정지 / 초기화

```powershell
docker compose stop            # 컨테이너만 정지 (데이터 유지)
docker compose down            # 컨테이너 제거 (볼륨 유지)
docker compose down -v         # 볼륨까지 삭제 (비밀번호/데이터 초기화)
```

## 현재 상태 (v2, N1~N13 완료)

end-to-end 동작한다: 프로젝트 생성 → 자연어 지식 입력 → Claude 추출 미리보기 → 그래프에 MERGE
누적 → 지식 현황(표·개별 삭제) → 자연어 탐색(text-to-cypher, 읽기 전용). 구 v1(설문/스키마) 코드는
N6에서 완전히 제거됐다. 이후 표준 어휘 정규화(N9)·정량 속성 구조화(N10)·그래프 시각화 강화(N11)·
탐색 예시 질문 프리셋(N12)·디자인/다크모드 리프레시(N13)까지 반영됐다. 마일스톤 상세는
[`../PLAN.md`](../PLAN.md) §10 참조.
