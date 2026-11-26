"""Test setup: no database, no scheduler, no ingest token.

The feed is an in-memory cache (backend/feed.py); the cache is cleared
before every test so tests never share feed state and never hit the
live Arbeitnow API unless a test explicitly mocks the fetch.
"""

import pytest
from fastapi.testclient import TestClient

from backend import feed
from backend.main import app


@pytest.fixture(autouse=True)
def _clear_feed_cache():
    feed.clear_cache()
    yield
    feed.clear_cache()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
