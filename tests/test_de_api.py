"""API tests for the bilingual checker: routing (Auto/DE/EN), the German
rule path, mixed/unsupported languages, context checkboxes, limits and
HTML escaping. The ML path is monkeypatched so these tests do not load
the model artifacts.
"""

DE_SCAM = {
    "title": "Von zu Hause 500 Euro pro Tag verdienen",
    "description": (
        "Sofortige Zusage! Verdienen Sie 500 Euro pro Tag von zu Hause aus, "
        "ohne Erfahrung und ohne Vorkenntnisse. Zahlen Sie nur eine kleine "
        "Bearbeitungsgebühr von 99 Euro per Vorkasse, um sofort zu starten. "
        "Senden Sie außerdem ein Foto Ihres Personalausweises zur "
        "Identitätsprüfung per Video-Ident. Kontakt nur über WhatsApp."
    ),
}

EN_TEXT = {
    "title": "Working Student Data Analyst",
    "description": (
        "As a working student in our Data Analytics team in Erlangen you "
        "will support data collection, validation and reporting with SQL "
        "and Power BI. You will document your results, present them to the "
        "team in our weekly meeting, and help maintain our dashboards. The "
        "role is 15 to 20 hours per week, with flexible hours around your "
        "lectures."
    ),
}

FR_TEXT = {
    "title": "Étudiant en alternance",
    "description": (
        "Nous recherchons un étudiant en alternance pour notre équipe à "
        "Erlangen. Vous participerez à la collecte de données et à la "
        "préparation de rapports avec SQL et Power BI. Le poste est à temps "
        "partiel, 15 heures par semaine, avec des horaires flexibles autour "
        "de vos cours à l université."
    ),
}

MIXED_TEXT = {
    "title": "Heimarbeit und home office work",
    "description": (
        "Wir suchen Mitarbeiter für leichte Heimarbeit von zu Hause aus. Sie "
        "verdienen 500 Euro pro Tag ohne Erfahrung. We are looking for "
        "employees for easy home office work. You earn 500 euros per day "
        "with no experience needed. Sofortige Zusage ohne "
        "Vorstellungsgespräch. Immediate acceptance with no interview "
        "required. Tägliche Auszahlung. Daily payout."
    ),
}


def _fake_ml(monkeypatch):
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


def test_predict_auto_german_routes_to_de(client):
    r = client.post("/api/predict", json=DE_SCAM)
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "de"
    assert data["de_band"] == "high"
    assert data["de_critical"] >= 1
    assert data["de_advice"] is True
    assert data["de_advice_link"].startswith("https://www.verbraucherzentrale.de/")
    assert len(data["de_matched"]) >= 1
    assert "Rule-based" in data["method_label_en"]
    assert "fraud_probability" not in data  # never shown as a % chance
    assert data["detected_language"] == "de"


def test_predict_auto_english_routes_to_ml(monkeypatch, client):
    _fake_ml(monkeypatch)
    r = client.post("/api/predict", json=EN_TEXT)
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "ml"
    assert data["decision_score"] == 2.1
    assert data["risk_band"] == "high"
    assert "Machine-learning model" in data["method_label_en"]
    assert "93.1%" in data["method_label_en"]


def test_predict_explicit_en_routes_to_ml_even_for_german(monkeypatch, client):
    _fake_ml(monkeypatch)
    r = client.post("/api/predict", json={**DE_SCAM, "posting_language": "en"})
    assert r.status_code == 200
    assert r.json()["path"] == "ml"
    assert r.json()["decision_score"] == 2.1


def test_predict_explicit_de_routes_to_de_for_english(client):
    r = client.post("/api/predict", json={**EN_TEXT, "posting_language": "de"})
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "de"
    # The English text matches no German rule (no company details is
    # the only mild signal) -> "few".
    assert data["de_band"] == "few"


def test_predict_auto_french_is_unsupported(client):
    r = client.post("/api/predict", json=FR_TEXT)
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "unsupported"
    assert data["detected_language"] == "fr"
    assert data["language_ok"] is False
    assert data["de_band"] == "" and data["risk_band"] == ""


def test_predict_auto_mixed_needs_choice(client):
    r = client.post("/api/predict", json=MIXED_TEXT)
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "needs_choice"
    assert data["mixed"] is True
    assert data["language_ok"] is False
    assert data["de_band"] == "" and data["risk_band"] == ""


def test_predict_invalid_posting_language(client):
    r = client.post("/api/predict", json={**EN_TEXT, "posting_language": "xx"})
    assert r.status_code == 400


def test_predict_german_with_context_flags(client):
    base = {
        "title": "Aushilfe im Lager",
        "description": (
            "Wir suchen eine Aushilfe für unser Lager in Nürnberg, 12 Stunden "
            "pro Woche, 15 Euro pro Stunde. Sie sortieren Waren und bereiten "
            "Sendungen vor. Bewerbung an bewerbung@lager-beispiel.de. "
            "Logistik Beispiel GmbH, Hafenstraße 2, 90768 Fürth."
        ),
    }
    r = client.post("/api/predict", json={**base, "posting_language": "de"})
    assert r.json()["de_band"] == "few"
    r = client.post("/api/predict", json={
        **base, "posting_language": "de", "context_flags": ["asked_id"],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "de"
    assert data["de_band"] == "high"
    assert data["de_critical"] == 1
    assert data["de_advice"] is True
    assert [c["id"] for c in data["de_checkboxes"]] == ["asked_id"]
    # Unknown flags are ignored, not an error.
    r = client.post("/api/predict", json={
        **base, "posting_language": "de", "context_flags": ["not_a_flag"],
    })
    assert r.json()["de_band"] == "few"


def test_predict_german_char_limits(client):
    r = client.post("/api/predict", json={
        "description": "Zu kurz.", "posting_language": "de",
    })
    assert r.status_code == 400
    r = client.post("/api/predict", json={
        "description": "x" * 10_001, "posting_language": "de",
    })
    assert r.status_code == 400
    r = client.post("/api/predict", json={
        "description": "x" * 100, "posting_language": "de",
    })
    assert r.status_code == 200


def test_predict_german_html_returned_verbatim(client):
    # The evidence sentence is returned verbatim (JSON-encoded) so the
    # frontend can escape it on render; the backend must not strip it.
    text = (
        "Bitte machen Sie ein Video-Ident zur Identifizierung. "
        "<script>alert(1)</script> Senden Sie uns außerdem ein Foto Ihres "
        "Personalausweises zur Prüfung. Die Stelle ist in Teilzeit, 20 "
        "Stunden pro Woche, in Nürnberg, und wir freuen uns auf Sie."
    )
    r = client.post("/api/predict", json={
        "description": text, "posting_language": "de",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "de"
    assert data["de_band"] == "high"
    evidence = " ".join(m["evidence"] for m in data["de_matched"])
    assert "<script>alert(1)</script>" in evidence
