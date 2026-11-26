"""Feed tests: Arbeitnow mapping / Germany filter / dedupe, the
in-memory cache (TTL, lazy refresh, lock), stale-cache fallback on
upstream failure, and HTTP 503 when there is no cache at all.

No live network: the upstream fetch is monkeypatched (fetch_arbeitnow
or httpx.Client), and the API-level tests seed the cache directly.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

import backend.feed as feed
from backend.feed import UpstreamUnavailable

SAMPLE_RAW = [
    {
        "slug": "job-berlin-1", "company_name": "Acme GmbH",
        "title": "Werkstudent Data", "description": "<p>Analyse data.</p>",
        "remote": "False",
        "url": "https://www.arbeitnow.com/jobs/acme/1",
        "tags": "[]", "job_types": '["Full Time"]',
        "location": "Berlin, Germany", "created_at": "1795000000",
    },
    {
        "slug": "job-london-1", "company_name": "London Ltd",
        "title": "Developer", "description": "<p>Code.</p>",
        "remote": "False",
        "url": "https://www.arbeitnow.com/jobs/london/1",
        "tags": "[]", "job_types": '["Full Time"]',
        "location": "London, UK", "created_at": "1795000000",
    },
    {
        # Same slug as the first row: an in-feed duplicate.
        "slug": "job-berlin-1", "company_name": "Acme GmbH",
        "title": "Werkstudent Data", "description": "<p>Analyse data.</p>",
        "remote": "False",
        "url": "https://www.arbeitnow.com/jobs/acme/1",
        "tags": "[]", "job_types": '["Full Time"]',
        "location": "Berlin, Germany", "created_at": "1795000000",
    },
    {
        # Different slug, same normalised title/company/location.
        "slug": "job-berlin-2", "company_name": "Acme GmbH",
        "title": "Werkstudent Data!", "description": "<p>Analyse data.</p>",
        "remote": "False",
        "url": "https://www.arbeitnow.com/jobs/acme/2",
        "tags": "[]", "job_types": '["Full Time"]',
        "location": "Berlin, Germany", "created_at": "1795000000",
    },
    {
        # Remote with no location stated: kept.
        "slug": "job-remote-1", "company_name": "Remote Co",
        "title": "Support Agent", "description": "Help customers.",
        "remote": "True",
        "url": "https://www.arbeitnow.com/jobs/remote/1",
        "tags": "[]", "job_types": '["Part Time"]',
        "location": "", "created_at": "1795000000",
    },
]


def test_is_german():
    assert feed.is_german("Berlin, Germany", False)
    assert feed.is_german("Munich, Bavaria, Germany", False)
    assert feed.is_german("Nürnberg", False)
    assert feed.is_german("", True)  # remote, no location
    assert not feed.is_german("London, UK", False)
    assert not feed.is_german("Paris, France", False)
    assert not feed.is_german("Remote", True)  # remote but non-German location
    assert not feed.is_german("", False)


def test_map_category():
    assert feed.map_category(["internship"], "Marketing Intern") == "Internship"
    assert feed.map_category(["Werkstudent"], "Werkstudent IT") == "Werkstudent"
    assert feed.map_category(["Teilzeit"], "Aushilfe") == "Part-time"
    assert feed.map_category(["Full Time"], "Engineer") == "Full-time"
    assert feed.map_category(["berufserfahren"], "Senior Dev") == "Other"


def test_strip_html():
    assert feed.strip_html("<p>Hello <strong>world</strong></p>") == "Hello world"
    assert feed.strip_html("a&nbsp;b &amp; c") == "a b c"


def test_as_list():
    assert feed._as_list(["a", "b"]) == ["a", "b"]
    assert feed._as_list('["a", "b"]') == ["a", "b"]
    assert feed._as_list("[]") == []
    assert feed._as_list(None) == []
    assert feed._as_list("") == []


def test_normalise_filters_and_dedupes():
    jobs = feed.normalise_jobs(SAMPLE_RAW)
    # London dropped; slug duplicate and normalised-title duplicate dropped.
    assert [j["external_id"] for j in jobs] == ["job-berlin-1", "job-remote-1"]
    berlin = jobs[0]
    assert berlin["id"] == "arbeitnow:job-berlin-1"
    assert berlin["source"] == "arbeitnow"
    assert berlin["title"] == "Werkstudent Data"
    assert berlin["description"] == "Analyse data."
    assert berlin["category"] == "Werkstudent"  # title wins over "Full Time"
    assert berlin["posted_at"] == datetime.fromtimestamp(
        1795000000, tz=timezone.utc)
    assert berlin["location"] == "Berlin, Germany"
    # No risk fields anywhere in the feed shape.
    assert set(berlin.keys()) == {
        "id", "source", "external_id", "title", "company", "location",
        "url", "description", "category", "posted_at",
    }
    assert jobs[1]["category"] == "Part-time"


def test_get_feed_fetches_once_then_serves_cache(monkeypatch):
    calls = []

    def fake_fetch(max_pages=3):
        calls.append(max_pages)
        return SAMPLE_RAW

    monkeypatch.setattr(feed, "fetch_arbeitnow", fake_fetch)
    first = feed.get_feed()
    second = feed.get_feed()
    assert len(calls) == 1  # second call served from cache, no refetch
    assert calls[0] == 3  # at most 3 pages by default
    assert first["stale"] is False
    assert first["upstream_ok"] is True
    assert first["cached_at"] is not None
    assert len(first["jobs"]) == 2
    assert second["jobs"] == first["jobs"]


def test_get_feed_refreshes_after_ttl(monkeypatch):
    monkeypatch.setattr(feed, "fetch_arbeitnow", lambda max_pages=3: SAMPLE_RAW)
    first = feed.get_feed()
    # Age the cache past the TTL, then change the upstream payload.
    old = datetime.now(timezone.utc) - timedelta(seconds=601)
    feed.seed_cache(first["jobs"], cached_at=old)
    monkeypatch.setattr(feed, "fetch_arbeitnow", lambda max_pages=3: [])
    refreshed = feed.get_feed()
    assert refreshed["jobs"] == []
    assert refreshed["stale"] is False
    assert refreshed["upstream_ok"] is True


def test_fetch_arbeitnow_raises_on_http_error(monkeypatch):
    # Mock httpx itself: the upstream is down.
    class BrokenClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            raise httpx.ConnectError("connection refused", request=None)

    monkeypatch.setattr(httpx, "Client", BrokenClient)
    with pytest.raises(httpx.ConnectError):
        feed.fetch_arbeitnow()


def test_stale_cache_served_on_upstream_failure(monkeypatch, client):
    # Seed a cache, age it past the TTL, then break the upstream.
    jobs = feed.normalise_jobs(SAMPLE_RAW)
    old = datetime.now(timezone.utc) - timedelta(seconds=601)
    feed.seed_cache(jobs, cached_at=old)

    def broken_fetch(max_pages=3):
        raise httpx.ConnectError("connection refused", request=None)

    monkeypatch.setattr(feed, "fetch_arbeitnow", broken_fetch)
    result = feed.get_feed()
    assert result["stale"] is True
    assert result["upstream_ok"] is False
    assert len(result["jobs"]) == 2
    # The API still answers 200 with the stale feed flagged.
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json()["total"] == 2
    assert r.json()["stale"] is True


def test_no_cache_and_upstream_down_is_503(monkeypatch, client):
    def broken_fetch(max_pages=3):
        raise httpx.ConnectError("connection refused", request=None)

    monkeypatch.setattr(feed, "fetch_arbeitnow", broken_fetch)
    with pytest.raises(UpstreamUnavailable):
        feed.get_feed()
    r = client.get("/api/jobs")
    assert r.status_code == 503
    assert "currently unavailable" in r.json()["detail"]
    r = client.get("/api/jobs/arbeitnow:job-berlin-1")
    assert r.status_code == 503
    # Stats degrades to an empty feed instead of failing.
    r = client.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["total_jobs"] == 0
    assert r.json()["feed"]["upstream_ok"] is False
    assert r.json()["feed"]["cached_at"] is None


def test_filter_jobs_search_category_sort():
    jobs = feed.normalise_jobs(SAMPLE_RAW)
    assert len(feed.filter_jobs(jobs, q="acme")) == 1
    assert len(feed.filter_jobs(jobs, q="REMOTE")) == 1  # company match
    assert len(feed.filter_jobs(jobs, category="Part-time")) == 1
    assert len(feed.filter_jobs(jobs, category="Other")) == 0
    # Both rows share the same posted_at; sorting must not crash and
    # must be stable in both directions.
    assert feed.filter_jobs(jobs, sort="newest")[0]["posted_at"] == \
        feed.filter_jobs(jobs, sort="oldest")[0]["posted_at"]
