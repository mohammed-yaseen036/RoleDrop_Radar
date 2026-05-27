from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    database = tmp_path / "test.db"
    settings = Settings(app_env="test", database_url=f"sqlite:///{database}", frontend_url="http://testserver")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def user_headers():
    return {"X-Demo-User": "candidate-one", "X-Demo-Email": "candidate@example.com"}

