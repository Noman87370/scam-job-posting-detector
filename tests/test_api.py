"""API tests that do NOT load the model artifacts (except /api/stats,
which reports model_info like the old suite did).

The feed is seeded straight into the in-memory cache (backend/feed.py)
— no database, no network. The /api/predict tests monkeypatch the
scoring function so the endpoint contract is tested without loading
the .joblib files.
"""

from datetime import datetime, timezone

from backend import feed


def _seed_jobs():
    def job(job_id, title, company, location, category, posted):
        return {
            "id": f"arbeitnow:{job_id}",
            "source": "arbeitnow",
            "external_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "url": f"https://example.com/{job_id}",
            "description": "Data analysis with Python.",
            "category": category,
            "posted_at": datetime(2026, 11, posted, 9, 0, 0, tzinfo=timezone.utc),
        }

    feed.seed_cache([
        job("a1", "Werkstudent Data Analysis", "Acme GmbH",
            "Berlin, Germany", "Werkstudent", 19),
        job("a2", "Earn money fast from home", "Quick Cash Ltd",
            "Remote", "Full-time", 18),
        job("a3", "Internship Marketing", "Beta AG",
            "Munich, Germany", "Internship", 17),
    ])


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_jobs_empty_then_seeded(client):
    feed.seed_cache([])
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []
    assert r.json()["stale"] is False
    _seed_jobs()
    r = client.get("/api/jobs")
    assert r.json()["total"] == 3


def test_list_jobs_have_no_risk_fields(client):
    _seed_jobs()
    r = client.get("/api/jobs")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert set(item.keys()) == {
            "id", "source", "external_id", "title", "company",
            "location", "url", "description", "category", "posted_at",
        }
        assert isinstance(item["id"], str)
        assert item["id"].startswith("arbeitnow:")
    assert "cached_at" in r.json()
    assert r.json()["cached_at"] is not None


def test_search_by_title_company_location(client):
    _seed_jobs()
    assert client.get("/api/jobs", params={"q": "Werkstudent"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "Beta"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "Munich"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "werkstudent"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"q": "nonexistent"}).json()["total"] == 0


def test_category_filter(client):
    _seed_jobs()
    assert client.get("/api/jobs", params={"category": "Internship"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"category": "Werkstudent"}).json()["total"] == 1
    assert client.get("/api/jobs", params={"category": "Other"}).json()["total"] == 0


def test_no_risk_filters(client):
    # The old risk filters are gone: unknown query params are ignored
    # by FastAPI, and risk sort values are rejected.
    _seed_jobs()
    assert client.get("/api/jobs", params={"sort": "risk_desc"}).status_code == 422
    assert client.get("/api/jobs", params={"sort": "risk_asc"}).status_code == 422


def test_sorting_and_pagination(client):
    _seed_jobs()
    newest = client.get("/api/jobs", params={"sort": "newest"}).json()["items"]
    assert newest[0]["title"] == "Werkstudent Data Analysis"
    oldest = client.get("/api/jobs", params={"sort": "oldest"}).json()["items"]
    assert oldest[0]["title"] == "Internship Marketing"
    page1 = client.get("/api/jobs", params={"page": 1, "per_page": 2}).json()
    assert len(page1["items"]) == 2
    page2 = client.get("/api/jobs", params={"page": 2, "per_page": 2}).json()
    assert len(page2["items"]) == 1
    assert page2["items"][0]["id"] != page1["items"][0]["id"]
    # per_page is capped at 100.
    assert client.get("/api/jobs", params={"per_page": 101}).status_code == 422


def test_get_job_and_404(client):
    _seed_jobs()
    r = client.get("/api/jobs/arbeitnow:a1")
    assert r.status_code == 200
    assert r.json()["title"] == "Werkstudent Data Analysis"
    assert r.json()["id"] == "arbeitnow:a1"
    assert client.get("/api/jobs/arbeitnow:nope").status_code == 404


def test_stats(client):
    _seed_jobs()
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_jobs"] == 3
    assert data["active_jobs"] == 3
    assert data["by_category"]["Werkstudent"] == 1
    assert "by_risk_band" not in data
    assert "last_ingest" not in data
    assert "model" in data
    # Notebook metrics are the deployed model's metrics, not the
    # retrained run's (pr_auc 0.9141 / precision 0.9386 / recall 0.7589).
    assert data["model"]["metrics"]["pr_auc"] == 0.917
    assert data["model"]["metrics"]["precision"] == 0.931
    assert data["model"]["metrics"]["recall"] == 0.766
    assert data["model"]["metrics"]["source"] == "notebook"
    assert data["model"]["decision_threshold"] == 0.949
    feed_info = data["feed"]
    assert feed_info["source"] == "arbeitnow"
    assert feed_info["cached_at"] is not None
    assert isinstance(feed_info["cache_age_seconds"], int)
    assert feed_info["upstream_ok"] is True
    assert feed_info["stale"] is False


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


def test_ingest_endpoint_is_gone(client):
    r = client.post("/api/jobs/ingest")
    assert r.status_code in (404, 405)
