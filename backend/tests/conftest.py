from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import create_app
from app.repositories.estate import import_dataset


@pytest.fixture(scope="session")
def seeded_database(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("benchmark") / "seed.sqlite3"
    import_dataset(path, ROOT / "test-data")
    return path


@pytest.fixture
def settings(tmp_path, seeded_database):
    path = tmp_path / "test.sqlite3"
    shutil.copyfile(seeded_database, path)
    return Settings(database_path=path)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as session:
        yield session
