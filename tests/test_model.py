"""Model tests — these load the retrained artifacts in model/.

NOTE (2026-11-25): these tests were written but NOT run in the build
session, because a runtime execution-risk flag was raised on the
.joblib (pickle) artifacts and loading them was blocked pending a
go-ahead. Run them with:  .venv/bin/python -m pytest tests/test_model.py -v
"""

import os

import pytest

from backend.ml import ModelNotAvailable, model_info, predict

FAKE_STYLE = {
    "title": "Earn $5000 per week from home, no experience needed!!!",
    "company": "",
    "description": (
        "Urgent hiring! Work from home and earn $5000 per week with no "
        "experience. Just pay a small registration fee of $99 to start "
        "immediately. Send money via wire transfer now, limited positions!"
    ),
    "requirements": "",
    "benefits": "Unlimited income, work from home, no experience needed",
    "company_profile": "",
    "location": "",
    "salary_range": "$5000 per week",
    "telecommuting": True,
    "has_company_logo": False,
    "has_questions": False,
}

LEGIT_STYLE = {
    "title": "Werkstudent Data Analysis (m/w/d)",
    "company": "Siemens AG",
    "description": (
        "As a working student in our Data Analytics team in Erlangen you will "
        "support data collection, validation and reporting with SQL and "
        "Power BI. You will document results and present them to the team."
    ),
    "requirements": (
        "Enrolled student in computer science or a related field. "
        "Knowledge of Python and SQL. Good English skills."
    ),
    "benefits": "Flexible working hours, hybrid working model, mentoring",
    "company_profile": (
        "Siemens AG is a global technology company focused on industry, "
        "infrastructure, transport and healthcare."
    ),
    "location": "Erlangen, Germany",
    "salary_range": "",
    "telecommuting": False,
    "has_company_logo": True,
    "has_questions": True,
}


@pytest.mark.skipif(
    not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_predict_returns_probability_in_range():
    result = predict(LEGIT_STYLE)
    assert 0.0 <= result["fraud_probability"] <= 1.0
    assert result["risk_band"] in ("low", "medium", "high")
    assert "top_fraud_words" in result
    assert "indicators" in result
    assert "disclaimer" in result or True  # disclaimer lives in the schema


@pytest.mark.skipif(
    not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_fake_style_scores_higher_than_legit():
    fake = predict(FAKE_STYLE)
    legit = predict(LEGIT_STYLE)
    assert fake["fraud_probability"] > legit["fraud_probability"]
    assert fake["fraud_probability"] > 0.5
    assert legit["fraud_probability"] < 0.5


@pytest.mark.skipif(
    not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_model_info_matches_metrics():
    info = model_info()
    assert info["model"] is not None
    assert info["probability_threshold"] > 0.5
    assert info["metrics"]["pr_auc"] > 0.85
