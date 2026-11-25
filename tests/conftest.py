"""Test setup: temp SQLite DB, scheduler off, fixed ingest token.

The model artifacts are NOT loaded by these tests (see test_model.py,
which is the only file that loads them).
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_TMP = tempfile.mkdtemp(prefix="scamdetector-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["RUN_SCHEDULER"] = "false"
os.environ["INGEST_TOKEN"] = "test-token"

from backend.database import Base, engine  # noqa: E402
from backend.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
