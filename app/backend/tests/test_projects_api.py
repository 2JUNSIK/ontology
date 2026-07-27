"""projects 라우터의 입력 검증 (Neo4j 불필요).

body 스키마 검증(422)은 라우트 함수 진입 전에 수행되므로 Neo4j 연결이 없어도 검증된다.
실제 삭제/조회 왕복은 test_kg_integration(opt-in)에서 다룬다.
"""

import unicodedata

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.routers.projects import EntityRef, RelationRef

client = TestClient(app)


def test_delete_entity_rejects_empty_name():
    r = client.request("DELETE", "/api/projects/anyid/entities", json={"name": ""})
    assert r.status_code == 422


def test_delete_entity_requires_name():
    r = client.request("DELETE", "/api/projects/anyid/entities", json={})
    assert r.status_code == 422


def test_delete_relation_requires_all_fields():
    r = client.request("DELETE", "/api/projects/anyid/relations", json={"source": "A"})
    assert r.status_code == 422


def test_delete_relation_rejects_empty_type():
    r = client.request(
        "DELETE",
        "/api/projects/anyid/relations",
        json={"source": "A", "target": "B", "type": ""},
    )
    assert r.status_code == 422


def test_extract_rejects_empty_text():
    r = client.post("/api/projects/anyid/extract", json={"text": ""})
    assert r.status_code == 422


def test_query_rejects_empty_question():
    r = client.post("/api/projects/anyid/query", json={"question": ""})
    assert r.status_code == 422


def test_query_requires_question():
    r = client.post("/api/projects/anyid/query", json={})
    assert r.status_code == 422


def test_query_rejects_too_long_question():
    r = client.post("/api/projects/anyid/query", json={"question": "가" * 2001})
    assert r.status_code == 422


# ---- 삭제 요청모델 정규화(ingest와 대칭 — '조용한 무삭제' 방지) : Neo4j 불필요 ----


def test_entity_ref_trims_and_nfc_normalizes():
    # 앞뒤 공백 제거 + NFC 정규화 → 저장된 _name(항상 NFC/trim)과 일치하게 만든다.
    assert EntityRef(name="  녹조  ").name == "녹조"
    nfd = unicodedata.normalize("NFD", "녹조")
    assert nfd != "녹조"
    assert EntityRef(name=nfd).name == "녹조"


def test_entity_ref_rejects_control_and_zero_width():
    for bad in ["녹\x00조", "녹" + chr(0x200B) + "조", ""]:
        with pytest.raises(ValidationError):
            EntityRef(name=bad)


def test_relation_ref_normalizes_endpoints_and_type():
    r = RelationRef(source="  녹조  ", target="남조류", type="  원인  ")
    assert r.source == "녹조"
    assert r.type == "원인"


def test_relation_ref_type_rejects_backtick_and_underscore():
    with pytest.raises(ValidationError):
        RelationRef(source="A", target="B", type="원인`")
    with pytest.raises(ValidationError):
        RelationRef(source="A", target="B", type="_원인")
