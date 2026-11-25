"""Model tests — these load the artifacts in model/.

Run them with:  .venv/bin/python -m pytest tests/test_model.py -v
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
    "company": "Harborview Analytics GmbH",
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
        "Harborview Analytics is a mid-sized software company focused on "
        "data tools for manufacturers, based in Erlangen."
    ),
    "location": "Erlangen, Germany",
    "salary_range": "",
    "telecommuting": False,
    "has_company_logo": True,
    "has_questions": True,
}


@pytest.mark.skipif(
    not os.path.exists("model/model_artifacts.joblib")
    and not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_predict_returns_score_and_band():
    result = predict(LEGIT_STYLE)
    assert isinstance(result["decision_score"], float)
    assert result["risk_band"] in ("high", "some", "few")
    assert result["risk_label"] in (
        "High risk", "Some warning signs", "Few warning signs")
    assert result["threshold"] == 0.949
    assert "top_raising" in result
    assert "top_lowering" in result
    assert "indicators" in result
    assert result["language_ok"] is True


@pytest.mark.skipif(
    not os.path.exists("model/model_artifacts.joblib")
    and not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_fake_style_scores_higher_than_legit():
    fake = predict(FAKE_STYLE)
    legit = predict(LEGIT_STYLE)
    assert fake["decision_score"] > legit["decision_score"]
    assert fake["risk_band"] == "high"
    assert legit["risk_band"] == "few"
    assert fake["decision_score"] >= 0.949
    assert legit["decision_score"] < 0


@pytest.mark.skipif(
    not os.path.exists("model/model_artifacts.joblib")
    and not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_contributions_are_readable_and_signed():
    result = predict(FAKE_STYLE)
    assert len(result["top_raising"]) <= 5
    assert len(result["top_lowering"]) <= 3
    assert all(c["contribution"] > 0 for c in result["top_raising"])
    assert all(c["contribution"] < 0 for c in result["top_lowering"])
    # No raw meta column names leak into the explanation.
    names = [c["feature"] for c in result["top_raising"] + result["top_lowering"]]
    assert "no_profile" not in names
    assert "has_company_logo" not in names
    assert "no company profile provided" in names


@pytest.mark.skipif(
    not os.path.exists("model/model_artifacts.joblib")
    and not os.path.exists("model/logreg_model.joblib"),
    reason="model artifacts not present",
)
def test_model_info_reports_notebook_threshold():
    info = model_info()
    assert info["model"] is not None
    assert "LogisticRegression" in info["model"]
    assert info["decision_threshold"] == 0.949
    assert info["metrics"]["pr_auc"] > 0.85
