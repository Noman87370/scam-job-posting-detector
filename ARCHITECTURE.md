# Architecture — Scam Job Posting Detector

## Overview

A single-service web app: a FastAPI backend serves both the REST API and
the built React frontend (static files in `backend/static`). A
background scheduler ingests fresh job postings every 30 minutes, scores
each one with a retrained ML model, and stores the results. A GitHub
Actions cron calls the ingest endpoint on the same schedule so the
free-tier host wakes up.

```
Arbeitnow API ──► ingest.py ──► ml.py (TF-IDF + LogisticRegression)
                                  │
                                  ▼
React dashboard ◄── FastAPI (main.py) ◄── SQLite / Postgres (SQLAlchemy)
                                  ▲
                    GitHub Actions cron ── POST /api/jobs/ingest
                    APScheduler (in-process, every 30 min)
```

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12), Uvicorn |
| Database | SQLAlchemy 2.x; SQLite locally, Postgres via `DATABASE_URL` |
| Scheduler | APScheduler (in-process) + GitHub Actions cron |
| Frontend | React 19 + Vite 8, plain CSS, no component library |
| ML | scikit-learn (TF-IDF + LogisticRegression), joblib artifacts |
| Hosting | Render free web service + free Postgres (see DEPLOYMENT.md) |
| Tests | pytest + FastAPI TestClient |

## Data flow

1. **Ingest** (`backend/ingest.py`): fetches up to 10 pages × 300 jobs
   from `https://www.arbeitnow.com/api/job-board-api` (no key, updated
   hourly). Each posting is mapped to the model schema: HTML stripped,
   metadata flags computed from raw text with regex (URL/email/phone
   present, missing profile/requirements, salary present, text length,
   company logo), job type mapped to a category.
2. **Germany filter**: keep a posting if its location is in Germany or
   it is remote with no non-German location. A German-city list
   (Berlin, München, Hamburg, …) plus the words "Germany"/"Deutschland"
   decide this.
3. **Score** (`backend/ml.py`): the posting text is cleaned exactly as
   in training (lowercase, strip HTML, map URL/email/phone tokens,
   a-z only), vectorised with the saved TF-IDF vectorizer, and scored
   by the saved logistic regression model. The decision threshold is
   converted to a probability threshold (0.7373) via the sigmoid.
4. **Store** (`backend/models.py`): dedupe on `(source, external_id)`
   and on normalised `(title, company, location)`; update re-seen
   postings in place. Expiry: `posted_at` older than 60 days, or not
   seen in the latest full ingest + 7 days grace — marked `expired`,
   never deleted.
5. **Serve**: the API returns stored jobs; the dashboard filters/sorts
   them client-side from the API.

## Model

Trained from the Kaggle "Real / Fake Job Posting Prediction" dataset
(17,880 postings, 18 columns, ~4.8% fraudulent) by
`train/train_model.py`, reproducing the research notebook exactly:

- Text = title + company_profile + description + requirements +
  benefits, cleaned as above; duplicates/empties dropped before
  splitting (15,691 left; 12,552 train / 3,139 test, stratified,
  seed 42).
- Features: TF-IDF 1–2 grams (min_df=3, max_df=0.9, English stop
  words, sublinear, max 60k) + 10 metadata flags.
- Model: `LogisticRegression(C=5, class_weight="balanced",
  max_iter=1000)`.
- Threshold: max recall at precision ≥ 90% on 5-fold CV predictions.

Retrained results (see `model/METRICS.md`): **PR-AUC 0.914, precision
0.939, recall 0.759, F1 0.839** — 107 of 141 fake postings caught, 7
false alarms. The README's notebook claimed PR-AUC 0.917, precision
93.1%, recall 76.6% — the retrain reproduces it within noise.

**Risk bands**: high ≥ 0.7373 (probability threshold), medium ≥ 0.25,
low below. **Predictions are risk estimates, never a verdict** — the
API and UI both carry a disclaimer to that effect.

`backend/ml.py` also returns the top contributing words (from model
coefficients) and 9 rule-based indicators (upfront fee, wire transfer,
urgency language, unrealistic pay, no company profile, no
requirements, no logo, phone/email/URL tokens in text, very short
posting).

## API contract

Base: `/` (frontend at `/`, assets at `/assets/*`).

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | `{"status": "ok", "model_loaded": bool}` |
| GET | `/api/jobs` | List jobs. Params: `q` (title/company/location), `category`, `risk_band`, `min_risk`, `max_risk`, `sort` (newest/oldest/risk_desc/risk_asc), `page`, `per_page` (max 100). Returns `{items, total, page, per_page}`. |
| GET | `/api/jobs/{id}` | One job, 404 if missing. |
| POST | `/api/predict` | Body: title, company, description, requirements, benefits, location, salary info, flags. Returns fraud_probability 0–1, risk_band, probability_threshold, top_fraud_words, top_legit_words, indicators, disclaimer. |
| POST | `/api/jobs/ingest` | Header `X-Ingest-Token: <INGEST_TOKEN>`. Runs one ingest pass. Returns `{fetched, kept, inserted, updated, duplicates, expired_marked, runs}`. 401 without the token; 503 if no token is configured. |
| GET | `/api/stats` | `{total_jobs, active_jobs, expired_jobs, by_category, by_risk_band, last_ingest_at, model}` |

## Scheduler

- **In-process**: APScheduler `BackgroundScheduler`, interval from
  `INGEST_INTERVAL_MINUTES` (default 30), started in the app lifespan
  when `RUN_SCHEDULER=true`. Each run creates its own DB session and
  logs the counts.
- **External**: `.github/workflows/ingest.yml` runs every 30 minutes
  (`*/30 * * * *`) and POSTs to `/api/jobs/ingest` with the shared
  secret. This is the reliable trigger on free tiers that sleep.

## Project layout

```
scam-job-detector/
├── backend/            FastAPI app (config, database, models, schemas,
│                       ml, ingest, scheduler, main) + requirements.txt
├── common/             features.py — text cleaning + metadata flags,
│                       shared by training and inference
├── train/              train_model.py — reproduces the notebook pipeline
├── frontend/           React + Vite dashboard (builds to backend/static)
├── model/              tfidf_vectorizer.joblib, logreg_model.joblib,
│                       metadata.json, METRICS.md
├── tests/              pytest suite (API, ingestion, model)
├── .github/workflows/  ingest.yml — 30-minute cron
├── Dockerfile          multi-stage (Node build + Python runtime)
├── render.yaml         Render Blueprint (web service + Postgres)
├── requirements.txt    backend runtime deps
└── DEPLOYMENT.md / ARCHITECTURE.md / README.md
```

## Configuration

All settings are environment variables (see `.env.example`):
`DATABASE_URL`, `INGEST_TOKEN`, `MODEL_DIR`, `FRONTEND_DIR`,
`RUN_SCHEDULER`, `INGEST_INTERVAL_MINUTES`, `ARBEITNOW_MAX_PAGES`.

## Known limitations

- One ingestion source (Arbeitnow). Job types there are a messy
  German/English mix, so category mapping is best-effort.
- The model was trained on 2019-era English Kaggle data; German-language
  postings score mainly on the metadata flags and English tokens.
- The cross-source normalised-dedupe set lives in memory per ingest run.
- The frontend fetches up to 500 jobs per page and filters client-side;
  fine at this scale, not for tens of thousands of rows.
