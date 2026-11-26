"""FastAPI app: job search + ML scam detection.

Serves the API and, when built, the React frontend as static files
(single service). The model is loaded lazily — importing this module
never loads the model artifacts.

The job feed has no database: listings are fetched server-side from
the Arbeitnow API and held in an in-memory cache (backend/feed.py).
"""

import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

# common/ lives next to backend/; make it importable whatever the CWD is.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from common.features import merge_text
from . import config
from .de_rules import check_german
from .feed import (
    UPSTREAM_UNAVAILABLE_MESSAGE,
    UpstreamUnavailable,
    current_status,
    filter_jobs,
    get_feed,
    get_job,
)
from .language import analyze_language
from .ml import ModelNotAvailable, model_info, predict
from .schemas import (
    DE_METHOD_LABEL_DE,
    DE_METHOD_LABEL_EN,
    DISCLAIMER,
    DISCLAIMER_DE,
    ML_METHOD_LABEL_DE,
    ML_METHOD_LABEL_EN,
    FeedInfo,
    JobOut,
    JobsPage,
    PredictIn,
    PredictOut,
    StatsOut,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Scam Job Posting Detector",
    description=(
        "Scam Job Posting Detector (English ML model + German warning-sign "
        "checker). English postings are scored by a TF-IDF + logistic "
        "regression model trained on the Kaggle Real/Fake Job Posting "
        "dataset; German postings are checked against warning signs from "
        "German consumer advice centers (rule-based, no ML). Scores are "
        "risk estimates, never a definitive verdict. The live job "
        "listings come from the Arbeitnow API (Germany)."
    ),
    version="2.0.0",
)


@app.get("/health")
def health():
    try:
        info = model_info()
        model_loaded = info.get("model") is not None
    except Exception:  # noqa: BLE001
        model_loaded = False
    return {"status": "ok", "model_loaded": model_loaded}


@app.get("/api/jobs", response_model=JobsPage)
def list_jobs(
    q: Optional[str] = Query(None, description="Search title, company or location"),
    category: Optional[str] = Query(None),
    sort: str = Query("newest", pattern="^(newest|oldest)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    try:
        feed = get_feed()
    except UpstreamUnavailable:
        raise HTTPException(status_code=503, detail=UPSTREAM_UNAVAILABLE_MESSAGE)
    filtered = filter_jobs(feed["jobs"], q=q, category=category, sort=sort)
    total = len(filtered)
    page_items = filtered[(page - 1) * per_page: page * per_page]
    return JobsPage(
        total=total, page=page, per_page=per_page,
        items=[JobOut(**j) for j in page_items],
        stale=feed["stale"], cached_at=feed["cached_at"],
    )


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job_by_id(job_id: str):
    try:
        job = get_job(job_id)
    except UpstreamUnavailable:
        raise HTTPException(status_code=503, detail=UPSTREAM_UNAVAILABLE_MESSAGE)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut(**job)


# Paste-in form limits: at least 100 characters in total (the model
# needs real text), at most 10,000 (keeps one request small on the
# free tier). Feed listings are not scored, so no limit applies to them.
MIN_INPUT_CHARS = 100
MAX_INPUT_CHARS = 10_000

_INPUT_TEXT_FIELDS = (
    "title", "company", "description", "requirements", "benefits",
    "company_profile", "location", "salary_range",
)


@app.post("/api/predict", response_model=PredictOut)
def predict_posting(payload: PredictIn):
    fields = payload.model_dump()
    total_chars = sum(len(str(fields.get(f) or "")) for f in _INPUT_TEXT_FIELDS)
    if total_chars < MIN_INPUT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Please enter at least {MIN_INPUT_CHARS} characters in total "
                   f"({total_chars} given).",
        )
    if total_chars > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Please keep the total input under {MAX_INPUT_CHARS} characters "
                   f"({total_chars} given).",
        )
    posting_language = (payload.posting_language or "auto").lower()
    if posting_language not in ("auto", "de", "en"):
        raise HTTPException(
            status_code=400,
            detail="posting_language must be 'auto', 'de' or 'en'.",
        )
    raw_text = merge_text(fields)

    # --- Routing ------------------------------------------------------
    # Auto: detect (only on >=100 chars, which the limit above guarantees).
    # Mixed German+English or unsure detection -> ask the user to choose.
    # Any other language -> "not supported". An explicit choice wins.
    detected = None
    detected_confidence = 0.0
    mixed = False
    if posting_language == "auto":
        detected = analyze_language(raw_text)
        detected_confidence = detected["confidence"]
        mixed = detected["mixed"]
        code = detected["code"]
        if mixed or detected["unsure"]:
            return PredictOut(
                path="needs_choice",
                language_ok=False,
                language_message=(
                    "This text mixes German and English. Please choose the "
                    "posting language."
                    if mixed else
                    "We could not tell whether this text is German or English. "
                    "Please choose the posting language."
                ),
                detected_language=code,
                detected_confidence=detected_confidence,
                mixed=mixed,
                disclaimer=DISCLAIMER,
                disclaimer_de=DISCLAIMER_DE,
            )
        if code not in ("de", "en"):
            return PredictOut(
                path="unsupported",
                language_ok=False,
                language_message=(
                    "This checker supports German and English postings only."
                ),
                detected_language=code,
                detected_confidence=detected_confidence,
                disclaimer=DISCLAIMER,
                disclaimer_de=DISCLAIMER_DE,
            )
        posting_language = code

    # --- German rule-based path (no ML, no invented metrics) ----------
    if posting_language == "de":
        result = check_german(raw_text, payload.context_flags or [])
        return PredictOut(
            path="de",
            risk_band=result["band"],
            risk_label=result["band_label_en"],
            language="de",
            detected_language="de",
            detected_confidence=detected_confidence,
            method_label_de=DE_METHOD_LABEL_DE,
            method_label_en=DE_METHOD_LABEL_EN,
            disclaimer=DISCLAIMER,
            disclaimer_de=DISCLAIMER_DE,
            de_band=result["band"],
            de_band_label_de=result["band_label_de"],
            de_band_label_en=result["band_label_en"],
            de_critical=result["critical"],
            de_strong=result["strong"],
            de_mild=result["mild"],
            de_matched=result["matched"],
            de_checkboxes=result["checkboxes_applied"],
            de_advice=result["advice"],
            de_advice_link=result["advice_link"],
            de_few_note_de=result["few_note_de"],
            de_few_note_en=result["few_note_en"],
        )

    # --- English ML path (unchanged) ----------------------------------
    try:
        result = predict(fields)
    except ModelNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    # The checker response carries no fraud probability (it is not a
    # "% chance of scam"); predict() keeps it internally and it is never shown.
    return PredictOut(
        path="ml",
        decision_score=result["decision_score"],
        risk_band=result["risk_band"],
        risk_label=result["risk_label"],
        threshold=result["threshold"],
        top_raising=result["top_raising"],
        top_lowering=result["top_lowering"],
        indicators=result["indicators"],
        language=result["language"],
        language_ok=result["language_ok"],
        language_message=result["language_message"],
        detected_language=result["language"],
        detected_confidence=detected_confidence,
        method_label_de=ML_METHOD_LABEL_DE,
        method_label_en=ML_METHOD_LABEL_EN,
        disclaimer=DISCLAIMER,
        disclaimer_de=DISCLAIMER_DE,
    )


@app.get("/api/stats", response_model=StatsOut)
def stats():
    try:
        feed = get_feed()
        jobs = feed["jobs"]
        feed_info = FeedInfo(
            source="arbeitnow",
            cached_at=feed["cached_at"],
            cache_age_seconds=(
                None if feed["cached_at"] is None
                else int((datetime.now(timezone.utc) - feed["cached_at"]).total_seconds())
            ),
            upstream_ok=feed["upstream_ok"],
            stale=feed["stale"],
        )
    except UpstreamUnavailable:
        # No cache and the upstream is down: report an empty feed with
        # upstream_ok=false instead of failing the stats call.
        jobs = []
        status = current_status()
        status["upstream_ok"] = False
        feed_info = FeedInfo(**status)
    by_category = dict(Counter(j["category"] for j in jobs))
    return StatsOut(
        total_jobs=len(jobs),
        active_jobs=len(jobs),
        by_category=by_category,
        model=model_info(),
        feed=feed_info,
    )


# --- Frontend (production build served as static files) -------------------
if os.path.isdir(config.FRONTEND_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(config.FRONTEND_DIR, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path in ("health", "docs", "openapi.json"):
            raise HTTPException(status_code=404, detail="Not found")
        index = os.path.join(config.FRONTEND_DIR, "index.html")
        # Resolve the requested file and reject anything outside the
        # frontend directory (e.g. "../" in the path).
        frontend_root = os.path.realpath(config.FRONTEND_DIR)
        candidate = os.path.realpath(os.path.join(frontend_root, full_path))
        if os.path.commonpath([candidate, frontend_root]) != frontend_root:
            raise HTTPException(status_code=404, detail="Not found")
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        if os.path.isfile(index):
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend not built")
