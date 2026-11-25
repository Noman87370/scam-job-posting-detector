"""Smoke test — scores 3 sample inputs and checks the output is stable.

The scam-like and normal samples are the same texts as the fictional
examples in frontend/src/App.jsx, so this test also verifies that the
examples shown in the UI land in the band they claim.

Run:  .venv/bin/python -m pytest tests/test_smoke.py -v
"""

import os

import pytest

from backend.ml import predict

# Same text as the "Scam-like example (fictional)" button in the UI.
SCAM_LIKE = {
    "title": "Earn $4,500 per week working from home — no experience needed",
    "company": "BrightPath Rewards",
    "location": "Remote",
    "description": (
        "Urgent hiring! Work from home and earn $4,500 per week with no "
        "experience needed. Just pay a small registration fee of $99 to start "
        "immediately. Send the money via wire transfer now — limited positions, "
        "apply today! Contact us on WhatsApp +1 555 010 2030 or email "
        "apply@brightpath-rewards.example to get started and earn money fast."
    ),
    "requirements": "",
    "benefits": "Unlimited income, work from home, no experience needed",
    "company_profile": "",
    "salary_range": "$4,500 per week",
    "telecommuting": True,
    "has_company_logo": False,
    "has_questions": False,
    "has_salary": True,
}

# Same text as the "Normal example (fictional)" button in the UI.
NORMAL = {
    "title": "Working Student Data Analyst (m/f/d)",
    "company": "Harborview Analytics GmbH",
    "location": "Erlangen, Germany",
    "description": (
        "As a working student in our Data Analytics team in Erlangen you will "
        "support data collection, validation and reporting with SQL and "
        "Power BI. You will document your results, present them to the team in our "
        "weekly meeting, and help maintain our dashboards. The role is 15 to "
        "20 hours per week, with flexible hours around your lectures and a "
        "hybrid working model."
    ),
    "requirements": (
        "Enrolled student in computer science, data science or a related "
        "field. Knowledge of Python and SQL. Good English skills; German is "
        "a plus but not required."
    ),
    "benefits": "Flexible working hours, hybrid working model, mentoring, €16 per hour",
    "company_profile": (
        "Harborview Analytics is a mid-sized software company in Erlangen "
        "that builds data tools for manufacturers. Our team of 40 works "
        "closely with customers across Germany."
    ),
    "salary_range": "€16 per hour",
    "telecommuting": True,
    "has_company_logo": True,
    "has_questions": True,
    "has_salary": True,
}

GERMAN = {
    "title": "Werkstudent (m/w/d) im Bereich Datenanalyse",
    "company": "Beispiel GmbH",
    "location": "Nürnberg, Deutschland",
    "description": (
        "Wir suchen einen Werkstudenten zur Unterstützung unseres Teams in "
        "Nürnberg. Sie arbeiten mit SQL und Python, erstellen Auswertungen "
        "und präsentieren die Ergebnisse im Team. Die Stelle ist auf 15 bis "
        "20 Stunden pro Woche ausgelegt und bietet flexible Arbeitszeiten."
    ),
    "requirements": (
        "Eingeschriebener Student der Informatik oder eines verwandten Fachs. "
        "Kenntnisse in Python und SQL. Gute Deutschkenntnisse."
    ),
    "benefits": "Flexible Arbeitszeiten, Mentoring, 16 Euro pro Stunde",
    "company_profile": (
        "Die Beispiel GmbH ist ein mittelständisches Softwareunternehmen in "
        "Nürnberg mit 40 Mitarbeitern."
    ),
    "salary_range": "16 Euro pro Stunde",
    "telecommuting": False,
    "has_company_logo": True,
    "has_questions": True,
    "has_salary": True,
}

NEEDS_MODEL = pytest.mark.skipif(
    not os.path.exists("model/model_artifacts.joblib")
    and not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)


@NEEDS_MODEL
def test_smoke_scam_like_is_high_risk():
    result = predict(SCAM_LIKE)
    assert result["risk_band"] == "high"
    assert result["decision_score"] >= 0.949
    assert result["language_ok"] is True


@NEEDS_MODEL
def test_smoke_normal_is_few_warning_signs():
    result = predict(NORMAL)
    assert result["risk_band"] == "few"
    assert result["decision_score"] < 0
    assert result["language_ok"] is True


@NEEDS_MODEL
def test_smoke_german_is_flagged_not_english():
    result = predict(GERMAN)
    assert result["language"] == "de"
    assert result["language_ok"] is False
    assert "trained on English postings" in result["language_message"]


@NEEDS_MODEL
def test_smoke_output_is_stable():
    first = predict(SCAM_LIKE)
    second = predict(SCAM_LIKE)
    assert first["decision_score"] == second["decision_score"]
    assert first["risk_band"] == second["risk_band"]
    assert first["top_raising"] == second["top_raising"]
    assert first["top_lowering"] == second["top_lowering"]
    normal = predict(NORMAL)
    assert first["decision_score"] > normal["decision_score"]
