"""FastAPI app: job search + ML scam detection.

Serves the API and, when built, the React frontend as static files
(single service). The model is loaded lazily — importing this module
never loads the model artifacts.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import config
from .database import Base, engine, get_db
from .ingest import ingest_arbeitnow
from .ml import ModelNotAvailable, model_info, predict
from .models import IngestRun, Job
from .schemas import (
    IngestOut,
    JobOut,
    JobsPage,
    PredictIn,
    PredictOut,
    StatsOut,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    if config.RUN_SCHEDULER:
        from .scheduler import start_scheduler

        _scheduler = start_scheduler()
        logger.info("Scheduler enabled")
    else:
        logger.info("Scheduler disabled (RUN_SCHEDULER=false)")
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title="Scam Job Posting Detector",
    description=(
        "AI-powered job search with fraud detection. Predictions are risk "
        "estimates from a TF-IDF + logistic regression model trained on the "
        "Kaggle Real/Fake Job Posting dataset — never a definitive verdict."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    try:
        info = model_info()
        model_loaded = info.get("model") is not None
    except Exception:  # noqa: BLE001
        model_loaded = False
    return {"status": "ok", "model_loaded": model_loaded}


def _job_out(job: Job) -> JobOut:
    data = {
        "id": job.id,
        "source": job.source,
        "external_id": job.external_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "url": job.url,
        "description": job.description,
        "category": job.category,
        "posted_at": job.posted_at,
        "fetched_at": job.fetched_at,
        "fraud_probability": job.fraud_probability,
        "risk_band": job.risk_band,
        "indicators": json.loads(job.indicators or "{}"),
        "expired": job.expired,
    }
    return JobOut(**data)


@app.get("/api/jobs", response_model=JobsPage)
def list_jobs(
    q: Optional[str] = Query(None, description="Search title, company or location"),
    category: Optional[str] = Query(None),
    min_risk: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_risk: Optional[float] = Query(None, ge=0.0, le=1.0),
    risk_band: Optional[str] = Query(None),
    sort: str = Query("newest", pattern="^(newest|oldest|risk_desc|risk_asc)$"),
    include_expired: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if not include_expired:
        query = query.filter(Job.expired.is_(False))
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Job.title.ilike(like)) | (Job.company.ilike(like)) | (Job.location.ilike(like))
        )
    if category:
        query = query.filter(Job.category == category)
    if min_risk is not None:
        query = query.filter(Job.fraud_probability >= min_risk)
    if max_risk is not None:
        query = query.filter(Job.fraud_probability <= max_risk)
    if risk_band:
        query = query.filter(Job.risk_band == risk_band)
    total = query.count()
    order = {
        "newest": Job.posted_at.desc(),
        "oldest": Job.posted_at.asc(),
        "risk_desc": Job.fraud_probability.desc(),
        "risk_asc": Job.fraud_probability.asc(),
    }[sort]
    items = (
        query.order_by(order)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return JobsPage(
        total=total, page=page, per_page=per_page,
        items=[_job_out(j) for j in items],
    )


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)


@app.post("/api/predict", response_model=PredictOut)
def predict_posting(payload: PredictIn):
    try:
        result = predict(payload.model_dump())
    except ModelNotAvailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return PredictOut(**result)


@app.post("/api/jobs/ingest", response_model=IngestOut)
def trigger_ingest(x_ingest_token: Optional[str] = Header(None)):
    if not config.INGEST_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Ingestion is disabled: INGEST_TOKEN is not configured.",
        )
    if x_ingest_token != config.INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid ingest token")
    try:
        result = ingest_arbeitnow()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Manual ingest failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return IngestOut(**result)


@app.get("/api/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Job.id)).scalar() or 0
    active = db.query(func.count(Job.id)).filter(Job.expired.is_(False)).scalar() or 0
    by_category = dict(
        db.query(Job.category, func.count(Job.id))
        .filter(Job.expired.is_(False))
        .group_by(Job.category)
        .all()
    )
    by_risk = dict(
        db.query(Job.risk_band, func.count(Job.id))
        .filter(Job.expired.is_(False))
        .group_by(Job.risk_band)
        .all()
    )
    last = (
        db.query(IngestRun)
        .order_by(IngestRun.started_at.desc())
        .first()
    )
    return StatsOut(
        total_jobs=total,
        active_jobs=active,
        by_category=by_category,
        by_risk_band=by_risk,
        last_ingest=last.finished_at if last else None,
        model=model_info(),
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
        candidate = os.path.join(config.FRONTEND_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        if os.path.isfile(index):
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend not built")
