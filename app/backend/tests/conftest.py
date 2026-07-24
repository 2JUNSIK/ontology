"""테스트 공통 설정.

안전장치: 테스트 중 실제 Claude API를 호출하지 않도록 모든 테스트에서 ANTHROPIC_API_KEY를
빈 값으로 만든다(비용/네트워크 차단). Claude 경로를 실제로 검증하는 테스트는 이 fixture를
덮어써서 더미 키 + 모킹된 클라이언트를 사용한다.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _block_live_claude(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "", raising=False)


@pytest.fixture(autouse=True)
def _reset_session_schema():
    """인메모리 세션 스키마(routers.schema._current_schema)를 테스트마다 초기화한다.

    프로세스 전역 mutable 상태라 테스트 순서 의존 오염을 막기 위함(단일 사용자 MVP).
    """
    from app.models import OntologySchema
    from app.routers import schema as schema_router

    schema_router._current_schema = OntologySchema()
    yield
