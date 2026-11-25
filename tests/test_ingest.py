"""Ingestion tests. The live API fetch and the ML scorer are both
monkeypatched, so these tests run without network and without loading
the model artifacts.
"""

import json

import backend.ingest as ingest
from backend.database import SessionLocal
from backend.models import Job


def test_is_german():
    assert ingest.is_german("Berlin, Germany", False)
    assert ingest.is_german("Munich, Bavaria, Germany", False)
    assert ingest.is_german("Nürnberg", False)
    assert ingest.is_german("", True)  # remote, no location
    assert not ingest.is_german("London, UK", False)
    assert not ingest.is_german("Paris, France", False)
    assert not ingest.is_german("Remote", True)  # remote but non-German location
    assert not ingest.is_german("", False)


def test_map_category():
    assert ingest.map_category(["internship"], "Marketing Intern") == "Internship"
    assert ingest.map_category(["Werkstudent"], "Werkstudent IT") == "Werkstudent"
    assert ingest.map_category(["Teilzeit"], "Aushilfe") == "Part-time"
    assert ingest.map_category(["Full Time"], "Engineer") == "Full-time"
    assert ingest.map_category(["berufserfahren"], "Senior Dev") == "Other"


def test_strip_html():
    assert ingest.strip_html("<p>Hello <strong>world</strong></p>") == "Hello world"
    assert ingest.strip_html("a&nbsp;b &amp; c") == "a b c"


def test_as_list():
    assert ingest._as_list(["a", "b"]) == ["a", "b"]
    assert ingest._as_list('["a", "b"]') == ["a", "b"]
    assert ingest._as_list("[]") == []
    assert ingest._as_list(None) == []
    assert ingest._as_list("") == []


SAMPLE_JOBS = [
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
        "slug": "job-berlin-1", "company_name": "Acme GmbH",
        "title": "Werkstudent Data", "description": "<p>Analyse data.</p>",
        "remote": "False",
        "url": "https://www.arbeitnow.com/jobs/acme/1",
        "tags": "[]", "job_types": '["Full Time"]',
        "location": "Berlin, Germany", "created_at": "1795000000",
    },
]


def _fake_score(fields):
    return {
        "fraud_probability": 0.05, "risk_band": "low",
        "probability_threshold": 0.737,
        "top_fraud_words": [], "top_legit_words": [],
        "indicators": [],
    }


def test_ingest_filters_stores_dedupes(monkeypatch):
    monkeypatch.setattr(ingest, "fetch_arbeitnow", lambda max_pages=10: SAMPLE_JOBS)
    monkeypatch.setattr(ingest, "predict", _fake_score)
    db = SessionLocal()
    db.query(Job).delete()
    db.commit()
    result = ingest.ingest_arbeitnow(db=db)
    # 3 fetched, 2 kept (London dropped), 1 inserted, 1 in-feed duplicate.
    assert result["fetched"] == 3
    assert result["kept"] == 2
    assert result["inserted"] == 1
    assert result["updated"] == 0
    assert result["duplicates"] == 1
    jobs = db.query(Job).all()
    assert len(jobs) == 1
    assert jobs[0].title == "Werkstudent Data"
    assert jobs[0].location == "Berlin, Germany"
    assert jobs[0].fraud_probability == 0.05
    assert json.loads(jobs[0].indicators)["top_fraud_words"] == []
    # Second run: same job is an update, not a new insert.
    result2 = ingest.ingest_arbeitnow(db=db)
    assert result2["inserted"] == 0
    assert result2["updated"] == 1
    assert result2["duplicates"] == 1
    db.close()
