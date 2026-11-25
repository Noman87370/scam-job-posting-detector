"""ML scoring — wraps the retrained model artifacts in model/.

The model is loaded lazily on first use so that importing this module (and
running the API without the model present) never fails. Predictions are
risk estimates, never certainty.

Risk bands (probability thresholds are documented in ARCHITECTURE.md):
  high   : p >= probability_threshold from model/metadata.json (0.737)
  medium : p >= 0.25
  low    : p <  0.25

Top contributing words come from the logistic-regression coefficients:
for the words present in the input text, contribution = tfidf_value * coef.
Positive contributions push towards fraud, negative towards legitimate.
"""

import json
import os
import re
import sys

import numpy as np
from scipy.sparse import csr_matrix, hstack

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.features import META_COLS, build_features  # noqa: E402
from .config import MODEL_DIR  # noqa: E402

MEDIUM_CUTOFF = 0.25

_model = None
_vectorizer = None
_metadata = None
_feature_names = None


class ModelNotAvailable(Exception):
    pass


def _load():
    global _model, _vectorizer, _metadata, _feature_names
    if _model is not None:
        return _model, _vectorizer, _metadata
    import joblib

    vec_path = os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib")
    mod_path = os.path.join(MODEL_DIR, "logreg_model.joblib")
    meta_path = os.path.join(MODEL_DIR, "metadata.json")
    if not (os.path.exists(vec_path) and os.path.exists(mod_path) and os.path.exists(meta_path)):
        raise ModelNotAvailable(
            f"Model artifacts not found in {MODEL_DIR}. Run train/train_model.py first."
        )
    _vectorizer = joblib.load(vec_path)
    _model = joblib.load(mod_path)
    with open(meta_path) as f:
        _metadata = json.load(f)
    # Built once: list() over the 60k TF-IDF vocabulary on every predict
    # added ~0.1s per call.
    _feature_names = list(_vectorizer.get_feature_names_out()) + META_COLS
    return _model, _vectorizer, _metadata


def model_info() -> dict:
    """Metadata about the model (no artifact loading beyond the JSON)."""
    meta_path = os.path.join(MODEL_DIR, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        return {
            "model": meta.get("model"),
            "dataset": meta.get("dataset"),
            "probability_threshold": meta.get("probability_threshold"),
            "metrics": meta.get("metrics"),
            "top_fraud_signals": meta.get("top_fraud_signals"),
            "top_legit_signals": meta.get("top_legit_signals"),
        }
    return {"model": None, "error": "metadata.json not found"}


def risk_band(probability: float, threshold: float) -> str:
    if probability >= threshold:
        return "high"
    if probability >= MEDIUM_CUTOFF:
        return "medium"
    return "low"


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
    """Score one posting. Returns probability, band, top words, indicators."""
    model, vec, meta = _load()
    clean, meta_vec = build_features(fields)
    X = hstack([vec.transform([clean]), csr_matrix(np.array([meta_vec], dtype=float))]).tocsr()
    proba = float(model.predict_proba(X)[0, 1])
    threshold = float(meta["probability_threshold"])

    # Top contributing words: tfidf value * coefficient for words present.
    feature_names = _feature_names
    coef = model.coef_[0]
    row = X[0].tocoo()
    # NOTE: len(vec.get_feature_names_out()) must be hoisted out of the
    # comprehension — it rebuilds a 60k-element array on every call, so
    # evaluating it per non-zero feature made a single predict take
    # seconds and a full ingest take over an hour.
    n_tfidf = len(vec.get_feature_names_out())
    contribs = [
        (feature_names[i], float(row.data[k] * coef[i]))
        for k, i in enumerate(row.col)
        if i < n_tfidf
    ]
    contribs.sort(key=lambda t: t[1], reverse=True)
    top_fraud = [{"word": w, "contribution": round(c, 4)} for w, c in contribs[:5] if c > 0]
    top_legit = [
        {"word": w, "contribution": round(c, 4)}
        for w, c in sorted(contribs, key=lambda t: t[1])[:5] if c < 0
    ]

    return {
        "fraud_probability": round(proba, 4),
        "risk_band": risk_band(proba, threshold),
        "probability_threshold": threshold,
        "top_fraud_words": top_fraud,
        "top_legit_words": top_legit,
        "indicators": rule_indicators(fields, clean),
    }
