"""API tests that do NOT load the model artifacts.

The /api/predict test monkeypatches the scoring function so the endpoint
contract is tested without loading the .joblib files.
"""

import json
from datetime import datetime

from backend.database import SessionLocal
from backend.models import Job


def _seed_jobs():
    db = SessionLocal()
    db.query(Job).delete()
    now = datetime(2026, 11, 20, 12, 0, 0)
    rows = [
        Job(source="arbeitnow", external_id="a1", title="Werkstudent Data Analysis",
            company="Acme GmbH", location="Berlin, Germany",
            url="https://example.com/a1", description="Data analysis with Python.",
            category="Werkstudent", posted_at=datetime(2026, 11, 19, 9, 0, 0),
            fetched_at=now, fraud_probability=0.05, risk_band="low", indicators="{}"),
        Job(source="arbeitnow", external_id="a2", title="Earn money fast from home",
            company="Quick Cash Ltd", location="Remote",
            url="https://example.com/a2", description="Send a fee to start.",
            category="Full-time", posted_at=datetime(2026, 11, 18, 9, 0, 0),
            fetched_at=now, fraud_probability=0.92, risk_band="high", indicators="{}"),
        Job(source="arbeitnow", external_id="a3", title="Internship Marketing",
            company="Beta AG", location="Munich, Germany",
            url="https://example.com/a3", description="Marketing internship.",
            category="Internship", posted_at=datetime(2026, 11, 17, 9, 0, 0),
            fetched_at=now, fraud_probability=0.40, risk_band="medium", indicators="{}"),
    ]
    db.add_all(rows)
    db.commit()
    ids = [r.id for r in rows]
    db.close()
    return ids


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_jobs_empty_then_seeded(client):
    db = SessionLocal()
    db.query(Job).delete()
    db.commit()
    db.close()
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []
    _seed_jobs()
    r = client.get("/api/jobs")
    assert r.json()["total"] == 3


def test_search_by_title_company_location(client):
    _seed_jobs()
    assert client.get("/api/jobs", params={"q": "Werkstudent"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "Beta"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "Munich"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "nonexistent"}).json()["total"] == 0


def test_category_and_risk_filters(client):
    _seed_jobs()
    assert client.get("/api/jobs", params={"category": "Internship"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"risk_band": "high"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"min_risk": 0.5}).json()["total"] == 1
    assert client.get("/api/jobs", params={"max_risk": 0.1}).json()["total"] == 1


def test_sorting_and_pagination(client):
    _seed_jobs()
    newest = client.get("/api/jobs", params={"sort": "newest"}).json()["items"]
    assert newest[0]["title"] == "Werkstudent Data Analysis"
    riskiest = client.get("/api/jobs", params={"sort": "risk_desc"}).json()["items"]
    assert riskiest[0]["title"] == "Earn money fast from home"
    page1 = client.get("/api/jobs", params={"page": 1, "per_page": 2}).json()
    assert len(page1["items"]) == 2
    page2 = client.get("/api/jobs", params={"page": 2, "per_page": 2}).json()
    assert len(page2["items"]) == 1
    assert page2["items"][0]["id"] != page1["items"][0]["id"]


def test_get_job_and_404(client):
    ids = _seed_jobs()
    r = client.get(f"/api/jobs/{ids[0]}")
    assert r.status_code == 200
    assert r.json()["title"] == "Werkstudent Data Analysis"
    assert client.get("/api/jobs/999999").status_code == 404


def test_stats(client):
    _seed_jobs()
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_jobs"] == 3
    assert data["active_jobs"] == 3
    assert data["by_category"]["Werkstudent"] == 1
    assert data["by_risk_band"]["high"] == 1
    assert "model" in data


def test_predict_endpoint_contract(monkeypatch, client):
    import backend.main as main

    def fake_predict(fields):
        return {
            "fraud_probability": 0.81,
            "risk_band": "high",
            "probability_threshold": 0.737,
            "top_fraud_words": [{"word": "fee", "contribution": 1.2}],
            "top_legit_words": [],
            "indicators": [],
        }

    monkeypatch.setattr(main, "predict", fake_predict)
    r = client.post("/api/predict", json={
        "title": "Earn money fast", "description": "Pay a fee to start.",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["fraud_probability"] == 0.81
    assert data["risk_band"] == "high"
    assert "disclaimer" in data


def test_ingest_requires_token(client):
    r = client.post("/api/jobs/ingest")
    assert r.status_code == 401
    r = client.post("/api/jobs/ingest", headers={"X-Ingest-Token": "wrong"})
    assert r.status_code == 401
