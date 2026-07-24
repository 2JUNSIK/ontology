"""환경변수 로드 (백엔드 전역 설정).

.env 는 app/ 디렉토리(docker-compose.yml, .env.example 과 같은 위치)에 둔다.
백엔드를 app/backend 에서 실행해도 아래 ENV_FILE 절대경로로 정확히 찾는다.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# app/backend/app/config.py -> parents[2] == app/
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ontology_dev_pw"

    # Anthropic (M3에서 사용)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"


settings = Settings()
