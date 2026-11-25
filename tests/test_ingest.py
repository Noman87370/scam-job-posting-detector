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
        "decision_score": -2.9,
        "fraud_probability": 0.05, "risk_band": "few",
        "threshold": 0.949,
        "top_raising": [], "top_lowering": [],
        "indicators": [],
        "language": "en", "language_ok": True, "language_message": "",
    }


def test_score_listing_german_uses_rule_check():
    # A German listing is checked with the rule-based checker, not the
    # ML model: no probability, no decision score, band from the rules.
    fields = {
        "title": "Von zu Hause 500 Euro pro Tag verdienen",
        "company_profile": "",
        "description": (
            "Sofortige Zusage! Verdienen Sie 500 Euro pro Tag von zu Hause "
            "aus, ohne Erfahrung. Zahlen Sie eine Bearbeitungsgebühr von 99 "
            "Euro per Vorkasse. Senden Sie ein Foto Ihres Personalausweises "
            "zur Identitätsprüfung per Video-Ident."
        ),
        "requirements": "", "benefits": "", "company": "",
        "salary_range": "", "telecommuting": True,
        "has_company_logo": False, "has_questions": False,
    }
    score = ingest._score_listing(
        fields, fields["title"], fields["description"])
    assert score["language"] == "de"
    assert score["risk_band"] == "high"
    assert score["fraud_probability"] == 0.0
    assert score["decision_score"] is None
    indicators = json.loads(score["indicators"])
    assert indicators["method"] == "de"
    assert indicators["critical"] >= 1


def test_score_listing_english_uses_ml(monkeypatch):
    monkeypatch.setattr(ingest, "predict", _fake_score)
    fields = {
        "title": "Working Student Data Analyst",
        "company_profile": "A software company in Erlangen.",
        "description": (
            "As a working student in our Data Analytics team in Erlangen you "
            "will support data collection, validation and reporting with SQL "
            "and Power BI. You will document your results and present them "
            "to the team in our weekly meeting."
        ),
        "requirements": "", "benefits": "", "company": "",
        "salary_range": "", "telecommuting": False,
        "has_company_logo": True, "has_questions": True,
    }
    score = ingest._score_listing(
        fields, fields["title"], fields["description"])
    assert score["language"] == "en"
    assert score["risk_band"] == "few"
    assert score["fraud_probability"] == 0.05
    assert json.loads(score["indicators"])["method"] == "ml"


def test_backfill_german_rows_use_rule_check():
    # A German row stored with an old ML score (computed on German text,
    # which the English model cannot judge) is re-scored with the rules.
    from datetime import datetime

    db = SessionLocal()
    db.query(Job).delete()
    db.add(Job(
        source="arbeitnow", external_id="de-old", title="Paketagent gesucht",
        company="SchnellGeld", location="Berlin, Germany",
        url="https://example.com/de-old",
        description=(
            "Paketagent gesucht! Nehmen Sie Pakete an, packen Sie sie um und "
            "leiten Sie sie weiter. Warenagenten verdienen 300 Euro pro Tag, "
            "ganz bequem von zu Hause aus. Keine Erfahrung nötig."
        ),
        category="Other", posted_at=datetime(2026, 11, 19, 9, 0, 0),
        fetched_at=datetime(2026, 11, 20, 12, 0, 0),
        fraud_probability=0.92, decision_score=2.4, risk_band="high",
        language="de", indicators="{}",
    ))
    db.commit()
    updated = ingest._backfill_scores(db)
    assert updated == 1
    job = db.query(Job).filter(Job.external_id == "de-old").first()
    assert job.risk_band == "high"  # from the rules, not the ML score
    assert job.fraud_probability == 0.0
    assert job.decision_score is None
    assert json.loads(job.indicators)["method"] == "de"
    # A second backfill finds nothing to do.
    assert ingest._backfill_scores(db) == 0
    db.close()


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
    assert jobs[0].decision_score == -2.9
    assert jobs[0].risk_band == "few"
    assert jobs[0].language == "en"
    assert json.loads(jobs[0].indicators)["top_raising"] == []
    # Second run: same job is an update, not a new insert.
    result2 = ingest.ingest_arbeitnow(db=db)
    assert result2["inserted"] == 0
    assert result2["updated"] == 1
    assert result2["duplicates"] == 1
    db.close()
