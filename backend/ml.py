"""ML scoring — wraps the model artifacts in model/.

The model is loaded lazily on first use so that importing this module
(and running the API without the model present) never fails.

Artifact: model_artifacts.joblib, a dict exported from the research
notebook (see the notebook cell in the README):
  {"vec": vec, "model": best, "meta_cols": meta_cols,
   "threshold": float(t), "feature_names": feature_names}
If that file is absent, the legacy pair tfidf_vectorizer.joblib +
logreg_model.joblib (+ metadata.json) is used instead.

Model (verified): LogisticRegression(C=5, class_weight="balanced",
max_iter=1000) — NOT the LinearSVC that was also compared in the
notebook. It has coef_, so per-feature contributions are available.

Decision rule (notebook): score = model.decision_function(X); the
posting is "high risk" when score >= 0.949. For logistic regression
the decision score is the log-odds, so 0.949 is a predicted probability
of about 0.72. Class weighting means the probabilities are NOT
calibrated, so they are never shown as a "% chance of scam" — the UI
shows the risk band and the decision score only.

Risk bands (decision-function score):
  high : score >= 0.949  -> "High risk"
  some : 0 <= score < 0.949 -> "Some warning signs"
  few  : score < 0         -> "Few warning signs"
No band says "safe" or "not a scam".

Feature contributions: contribution of feature i = x_i * coef_i, over
all features (TF-IDF words and the 10 metadata flags). The top 5
raising and top 3 lowering features are returned with readable names.
"""

import json
import os
import re
import sys

import numpy as np
from scipy.sparse import csr_matrix, hstack

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.features import META_COLS, build_features, merge_text  # noqa: E402
from .config import MODEL_DIR  # noqa: E402
from .language import detect_language, language_name  # noqa: E402

# Notebook threshold (decision-function score). The artifact file may
# carry its own "threshold" (exported from the notebook); that value
# wins when present, otherwise this default is used.
DECISION_THRESHOLD = 0.949

# Readable names for the 10 metadata flags, for the explanation.
META_LABELS = {
    "telecommuting": "remote work allowed",
    "has_company_logo": "company logo shown",
    "has_questions": "screening questions present",
    "has_url_token": "link in the posting",
    "has_email_token": "email address in the posting",
    "has_phone_token": "phone number in the posting",
    "no_profile": "no company profile provided",
    "no_requirements": "no requirements listed",
    "has_salary": "salary stated",
    "text_len": "posting text length",
}

RISK_LABELS = {
    "high": "High risk",
    "some": "Some warning signs",
    "few": "Few warning signs",
}

LANGUAGE_MESSAGE = (
    "This model was trained on English postings, so the result would "
    "be unreliable"
)

_model = None
_vectorizer = None
_metadata = None
_feature_names = None
_readable_names = None
_threshold = None
_artifact_file = None


class ModelNotAvailable(Exception):
    pass


def _load():
    global _model, _vectorizer, _metadata, _feature_names, _readable_names
    global _threshold, _artifact_file
    if _model is not None:
        return _model, _vectorizer, _metadata
    import joblib

    artifact_path = os.path.join(MODEL_DIR, "model_artifacts.joblib")
    vec_path = os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib")
    mod_path = os.path.join(MODEL_DIR, "logreg_model.joblib")
    meta_path = os.path.join(MODEL_DIR, "metadata.json")
    if os.path.exists(artifact_path):
        bundle = joblib.load(artifact_path)
        _vectorizer = bundle["vec"]
        _model = bundle["model"]
        _threshold = float(bundle.get("threshold", DECISION_THRESHOLD))
        meta_cols = list(bundle.get("meta_cols", META_COLS))
        _feature_names = list(
            bundle.get("feature_names")
            or (list(_vectorizer.get_feature_names_out()) + meta_cols)
        )
        _artifact_file = "model_artifacts.joblib"
    elif os.path.exists(vec_path) and os.path.exists(mod_path):
        _vectorizer = joblib.load(vec_path)
        _model = joblib.load(mod_path)
        # The notebook threshold, NOT the retrained threshold stored in
        # metadata.json (1.0322): the UI reports the notebook's numbers.
        _threshold = DECISION_THRESHOLD
        _feature_names = list(_vectorizer.get_feature_names_out()) + META_COLS
        _artifact_file = "tfidf_vectorizer.joblib + logreg_model.joblib"
    else:
        raise ModelNotAvailable(
            f"Model artifacts not found in {MODEL_DIR}. Run train/train_model.py "
            "first, or export model_artifacts.joblib from the notebook."
        )
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            _metadata = json.load(f)
    else:
        _metadata = {}
    # Readable names: TF-IDF features keep their word; metadata flags
    # get their plain-language label.
    _readable_names = [META_LABELS.get(n, n) for n in _feature_names]
    return _model, _vectorizer, _metadata


def decision_threshold() -> float:
    _load()
    return _threshold


def model_info() -> dict:
    """Metadata about the model (no artifact loading beyond the JSON)."""
    meta_path = os.path.join(MODEL_DIR, "metadata.json")
    info = {"model": None, "error": "metadata.json not found"}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        info = {
            "model": meta.get("model"),
            "dataset": meta.get("dataset"),
            "probability_threshold": meta.get("probability_threshold"),
            "metrics": meta.get("metrics"),
            "top_fraud_signals": meta.get("top_fraud_signals"),
            "top_legit_signals": meta.get("top_legit_signals"),
        }
    try:
        info["decision_threshold"] = decision_threshold()
        info["artifact_file"] = _artifact_file
    except ModelNotAvailable:
        info["decision_threshold"] = DECISION_THRESHOLD
        info["artifact_file"] = None
    return info


def risk_band(score: float, threshold: float = DECISION_THRESHOLD) -> str:
    """high / some / few, from the decision-function score."""
    if score >= threshold:
        return "high"
    if score >= 0:
        return "some"
    return "few"


_MONEY_RE = re.compile(
    r"(pay(ment)? (a |an |the )?(fee|deposit)|training fee|registration fee|"
    r"wire transfer|western union|moneygram|gift ?card|send money|bank (details|account)"
    r"|upfront (payment|fee|deposit))",
    re.IGNORECASE,
)
_URGENCY_RE = re.compile(
    r"(urgent(ly)?|immediate(ly)? (start|hiring)|limited (positions|spots|places)|"
    r"act (now|fast|quickly)|only \d+ (positions|spots) left|apply (now|today)!)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_URL_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)


def rule_indicators(fields: dict, clean: str) -> list[dict]:
    """Additional, factual fraud indicators beyond the model score.

    Each indicator states whether a concrete, checkable property is present
    in the posting. They are evidence, not a verdict.
    """
    raw = " ".join(str(fields.get(c) or "") for c in
                   ["title", "company_profile", "description", "requirements", "benefits"])
    indicators = [
        {
            "code": "no_company_profile",
            "label": "No company profile",
            "detail": "The posting gives no information about the employer.",
            "present": not str(fields.get("company_profile") or "").strip(),
        },
        {
            "code": "no_requirements",
            "label": "No requirements listed",
            "detail": "The posting lists no skills, experience or qualifications.",
            "present": not str(fields.get("requirements") or "").strip(),
        },
        {
            "code": "no_salary",
            "label": "No salary information",
            "detail": "No salary or pay range is stated.",
            "present": not str(fields.get("salary_range") or "").strip(),
        },
        {
            "code": "no_company_logo",
            "label": "No company logo",
            "detail": "The employer did not provide a company logo.",
            "present": not bool(fields.get("has_company_logo")),
        },
        {
            "code": "very_short_text",
            "label": "Very short posting",
            "detail": f"Posting text is only {len(clean)} characters after cleaning.",
            "present": len(clean) < 300,
        },
        {
            "code": "contains_url",
            "label": "Contains a link",
            "detail": "The text contains a URL. Check where it leads before clicking.",
            "present": bool(_URL_RE.search(raw)),
        },
        {
            "code": "contains_email",
            "label": "Contains an email address",
            "detail": "The text asks applicants to contact an email address directly.",
            "present": bool(_EMAIL_RE.search(raw)),
        },
        {
            "code": "asks_for_money",
            "label": "Asks for money or payment details",
            "detail": "The text mentions fees, deposits, wire transfers or bank details.",
            "present": bool(_MONEY_RE.search(raw)),
        },
        {
            "code": "urgency_language",
            "label": "High-pressure urgency language",
            "detail": "The text pressures applicants to act immediately.",
            "present": bool(_URGENCY_RE.search(raw)),
        },
    ]
    return indicators


def predict(fields: dict) -> dict:
    """Score one posting.

    Returns the decision score and risk band (never a verdict), the
    top features that raised/lowered the score, the rule-based
    indicators, and the detected language. fraud_probability is kept
    in the returned dict for feed sorting/storage only — the UI must
    never display it as a "% chance of scam".
    """
    model, vec, meta = _load()
    threshold = _threshold
    clean, meta_vec = build_features(fields)
    X = hstack([vec.transform([clean]), csr_matrix(np.array([meta_vec], dtype=float))]).tocsr()
    score = float(model.decision_function(X)[0])
    proba = float(model.predict_proba(X)[0, 1])
    band = risk_band(score, threshold)

    # Per-feature contributions: x_i * coef_i, over all features.
    # NOTE: len(vec.get_feature_names_out()) is hoisted out of the loop —
    # it rebuilds a 60k-element array on every call, so evaluating it per
    # non-zero feature made a single predict take seconds.
    coef = model.coef_[0]
    row = X[0].tocoo()
    contribs = [
        (_readable_names[i], float(row.data[k] * coef[i]))
        for k, i in enumerate(row.col)
    ]
    raising = [
        {"feature": name, "contribution": round(c, 4)}
        for name, c in sorted(contribs, key=lambda t: t[1], reverse=True)
        if c > 0
    ][:5]
    lowering = [
        {"feature": name, "contribution": round(c, 4)}
        for name, c in sorted(contribs, key=lambda t: t[1])
        if c < 0
    ][:3]

    raw_text = merge_text(fields)
    lang = detect_language(raw_text)
    language_ok = lang is None or lang == "en"

    return {
        "decision_score": round(score, 4),
        "fraud_probability": round(proba, 4),
        "risk_band": band,
        "risk_label": RISK_LABELS[band],
        "threshold": threshold,
        "top_raising": raising,
        "top_lowering": lowering,
        "indicators": rule_indicators(fields, clean),
        "language": lang,
        "language_ok": language_ok,
        "language_message": (
            "" if language_ok
            else f"{LANGUAGE_MESSAGE} (detected language: {language_name(lang)})"
        ),
    }
