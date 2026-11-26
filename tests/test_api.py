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
            fetched_at=now, fraud_probability=0.05, decision_score=-2.9,
            risk_band="few", language="en", indicators="{}"),
        Job(source="arbeitnow", external_id="a2", title="Earn money fast from home",
            company="Quick Cash Ltd", location="Remote",
            url="https://example.com/a2", description="Send a fee to start.",
            category="Full-time", posted_at=datetime(2026, 11, 18, 9, 0, 0),
            fetched_at=now, fraud_probability=0.92, decision_score=2.4,
            risk_band="high", language="en", indicators="{}"),
        Job(source="arbeitnow", external_id="a3", title="Internship Marketing",
            company="Beta AG", location="Munich, Germany",
            url="https://example.com/a3", description="Marketing internship.",
            category="Internship", posted_at=datetime(2026, 11, 17, 9, 0, 0),
            fetched_at=now, fraud_probability=0.40, decision_score=0.3,
            risk_band="some", language="de", indicators="{}"),
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
            "decision_score": 2.1,
            "fraud_probability": 0.89,
            "risk_band": "high",
            "risk_label": "High risk",
            "threshold": 0.949,
            "top_raising": [{"feature": "fee", "contribution": 1.2}],
            "top_lowering": [],
            "indicators": [],
            "language": "en",
            "language_ok": True,
            "language_message": "",
        }

    monkeypatch.setattr(main, "predict", fake_predict)
    r = client.post("/api/predict", json={
        "title": "Earn money fast",
        "description": "Pay a fee to start working from home and earn money fast "
                       "with no experience needed, apply now, limited positions.",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["decision_score"] == 2.1
    assert data["risk_band"] == "high"
    assert data["risk_label"] == "High risk"
    assert data["threshold"] == 0.949
    assert "fraud_probability" not in data  # never shown as a % chance
    assert data["language_ok"] is True
    assert "disclaimer" in data
    assert "misses about 1 in 4 scams" in data["disclaimer"]


def test_predict_rejects_too_short_and_too_long(monkeypatch, client):
    import backend.main as main

    def fake_predict(fields):
        return {
            "decision_score": -1.0,
            "fraud_probability": 0.27,
            "risk_band": "few",
            "risk_label": "Few warning signs",
            "threshold": 0.949,
            "top_raising": [],
            "top_lowering": [],
            "indicators": [],
            "language": "en",
            "language_ok": True,
            "language_message": "",
        }

    monkeypatch.setattr(main, "predict", fake_predict)
    r = client.post("/api/predict", json={"description": "Too short."})
    assert r.status_code == 400
    r = client.post("/api/predict", json={"description": "x" * 10_001})
    assert r.status_code == 400
    r = client.post("/api/predict", json={"description": "x" * 100})
    assert r.status_code == 200


def test_predict_german_routes_to_rule_check(monkeypatch, client):
    # German text with Auto now routes to the German rule checker, not
    # to the English ML model — so the monkeypatched ML predict must
    # NOT be called, and there is no "trained on English postings"
    # warning any more: the German path has its own result.
    import backend.main as main

    def fake_predict(fields):
        raise AssertionError("ML predict must not run for German text")

    monkeypatch.setattr(main, "predict", fake_predict)
    r = client.post("/api/predict", json={
        "title": "Werkstudent im Bereich Datenanalyse",
        "description": "Wir suchen einen Werkstudenten zur Unterstützung "
                       "unseres Teams in Nürnberg. Sie arbeiten mit SQL und "
                       "Python und präsentieren die Ergebnisse im Team.",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "de"
    assert data["detected_language"] == "de"
    assert data["de_band"] == "few"
    assert "Rule-based" in data["method_label_en"]
    assert "fraud_probability" not in data


def test_frontend_rejects_path_traversal(client):
    # A ".." in the path must not serve files outside the frontend dir.
    r = client.get("/..%2f..%2f..%2fetc%2fpasswd")
    assert r.status_code == 404
    assert "root:" not in r.text


def test_ingest_requires_token(client):
    r = client.post("/api/jobs/ingest")
    assert r.status_code == 401
    r = client.post("/api/jobs/ingest", headers={"X-Ingest-Token": "wrong"})
    assert r.status_code == 401
