from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(data_dir=tmp_path / "data", max_apk_bytes=1024)
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
