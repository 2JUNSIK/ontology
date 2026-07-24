"""API 엔드포인트 테스트 (FastAPI TestClient)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_survey_questions():
    r = client.get("/api/survey/questions")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 8
    q = {x["id"]: x for x in data}
    assert q["water_items"]["type"] == "multi"
    assert q["free_text"]["type"] == "text"
    assert q["assets"]["options"][0]["label"] == "저수지"


def test_suggest_returns_draft_and_empty_enrichment():
    payload = {"answers": {"assets": ["저수지"], "has_station": "예", "water_items": ["클로로필-a"]}}
    r = client.post("/api/suggest", json=payload)
    assert r.status_code == 200
    body = r.json()
    labels = {n["label"] for n in body["draft"]["nodes"]}
    assert {"저수지", "측정소", "수질항목"}.issubset(labels)
    # M2: Claude 보강은 아직 비어 있어야 함
    assert body["enrichment"]["suggestions"] == []
    assert "warnings" in body


def test_suggest_empty_answers_ok():
    r = client.post("/api/suggest", json={"answers": {}})
    assert r.status_code == 200
    assert r.json()["draft"]["nodes"] == []


def test_suggest_missing_answers_field_defaults_empty():
    # answers 필드를 아예 안 줘도 기본 빈 dict 로 동작
    r = client.post("/api/suggest", json={})
    assert r.status_code == 200
    assert r.json()["draft"]["nodes"] == []


def test_suggest_rejects_non_object_answers():
    r = client.post("/api/suggest", json={"answers": "저수지"})
    assert r.status_code == 422  # answers 는 object(또는 null) 여야 함


def test_suggest_null_answers_is_accepted_as_empty():
    # 프론트가 미응답을 null 로 보낼 수 있음 → 빈 draft 로 200 (M1 계약)
    r = client.post("/api/suggest", json={"answers": None})
    assert r.status_code == 200
    assert r.json()["draft"]["nodes"] == []


def test_suggest_injected_option_not_reflected():
    payload = {"answers": {"assets": ["<script>alert(1)</script>", "저수지"]}}
    r = client.post("/api/suggest", json=payload)
    assert r.status_code == 200
    labels = [n["label"] for n in r.json()["draft"]["nodes"]]
    assert labels == ["저수지"]                 # 주입 문자열은 라벨이 되지 않음
    assert "<script>" not in r.text            # 응답 본문에 그대로 반영되지 않음


def test_suggest_large_payload_collapses_to_one_node():
    payload = {"answers": {"assets": ["저수지"] * 10000}}
    r = client.post("/api/suggest", json=payload)
    assert r.status_code == 200
    assert len(r.json()["draft"]["nodes"]) == 1
