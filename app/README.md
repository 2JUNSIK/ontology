# Ontology Builder — app

K-water 녹조/수질 도메인 온톨로지 설계 웹앱. 전체 설계는 상위 폴더의 [`../PLAN.md`](../PLAN.md) 참조.

```
app/
├─ docker-compose.yml   # Neo4j 5 (community) — 7474(browser) / 7687(bolt)
├─ .env.example         # 복사해서 .env 작성
├─ backend/             # FastAPI (Python)
└─ frontend/            # React + Vite
```

## 사전 준비

- Docker Desktop (설치됨, AutoStart 꺼져 있으면 먼저 실행)
- Python 3.11+
- Node.js 18+

## 실행 (PowerShell)

```powershell
# 0) Docker Desktop이 꺼져 있으면 먼저 기동
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

# 1) 환경변수 준비
Copy-Item .env.example .env      # 이후 .env 안의 ANTHROPIC_API_KEY 채우기 (M3부터 필요)

# 2) Neo4j 기동 (neo4j:5-community 이미지 캐시됨 → 즉시 기동)
docker compose up -d
#    Neo4j Browser: http://localhost:7474  (user: neo4j / pw: .env의 NEO4J_PASSWORD)

# 3) 백엔드
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # http://localhost:8000/health, /docs

# 4) 프론트 (M5부터 실제 화면)
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

## 현재 상태 (M0)

인프라 스캐폴드 단계다. Neo4j 기동 + FastAPI `/health` 부팅까지 확인 가능.
설문/Claude 보강/Cypher 반영/그래프 시각화는 M1~M5에서 구현한다 (PLAN.md §10).
