# Architecture — Scam Job Posting Detector

## Overview

A single-service web app: a FastAPI backend serves both the REST API and
the built React frontend (static files in `backend/static`). A
background scheduler ingests fresh job postings every 30 minutes, scores
each one with the model, and stores the results. A GitHub Actions cron
calls the ingest endpoint on the same schedule so the free-tier host
wakes up. Visitors can also paste an English posting into a structured
form and get a risk level with an explanation.

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
| ML | scikit-learn (TF-IDF + LogisticRegression), joblib artifacts, langdetect |
| Hosting | Render free web service + free Postgres (see DEPLOYMENT.md) |
| Tests | pytest + FastAPI TestClient |

## Data flow

1. **Ingest** (`backend/ingest.py`): fetches up to 10 pages × 300 jobs
   from `https://www.arbeitnow.com/api/job-board-api` (free public API,
   no key, updated hourly). Each posting is mapped to the model schema:
   HTML stripped, metadata flags computed exactly as in training
   (real URLs/emails/phones converted to placeholders first — see
   `common/features.py`), job type mapped to a category. The
   Arbeitnow API returns no company profile or requirements, so those
   two flags are 1 for every ingested listing.
2. **Germany filter**: keep a posting if its location is in Germany or
   it is remote with no non-German location. A German-city list
   (Berlin, München, Hamburg, …) plus the words "Germany"/"Deutschland"
   decide this.
3. **Language** (`backend/language.py`): each listing's language is
   detected with langdetect and stored. The dashboard shows a risk band
   only for English listings; non-English listings show no risk level.
   Rows ingested before the language column existed are backfilled on
   the next ingest run (language from stored text; decision score
   recovered from the stored probability via log-odds).
4. **Score** (`backend/ml.py`): the posting text is cleaned exactly as
   in training (lowercase, strip HTML, map URL/email/phone tokens,
   a-z only), vectorised with the saved TF-IDF vectorizer, and scored
   by the saved logistic regression model. The decision threshold is
   the notebook's **0.949** (decision-function score). Contributions
   are x_i * coef_i over all features; the top 5 raising and top 3
   lowering features are returned with readable names.
5. **Store** (`backend/models.py`): dedupe on `(source, external_id)`
   and on normalised `(title, company, location)`; update re-seen
   postings in place. Expiry: `posted_at` older than 60 days, or not
   seen in the latest full ingest + 7 days grace — marked `expired`,
   never deleted. A startup migration (`ensure_job_columns`) adds the
   `decision_score` / `language` columns to databases created before
   them.
6. **Serve**: the API returns stored jobs; the dashboard filters/sorts
   them from the API. The paste-in form (`POST /api/predict`) accepts
   the structured fields, enforces 100–10,000 characters in total, and
   returns the decision score, risk band, feature contributions and
   the language check — never a probability as a "% chance of scam".

## Model

Trained from the Kaggle "Real / Fake Job Posting Prediction" dataset
(17,880 postings, 18 columns, ~4.8% fraudulent) by
`train/train_model.py`, reproducing the research notebook:

- Text = title + company_profile + description + requirements +
  benefits, cleaned as above; duplicates/empties dropped before
  splitting (15,691 left; 12,552 train / 3,139 test, stratified,
  seed 42).
- Features: TF-IDF 1–2 grams (min_df=3, max_df=0.9, English stop
  words, sublinear, max 60k) + 10 metadata flags.
- Model: `LogisticRegression(C=5, class_weight="balanced",
  max_iter=1000)` — the LinearSVC compared in the notebook is not used.
  Verified loaded: LogisticRegression, coef_ shape (1, 60010).
- Threshold: the notebook's 0.949 (decision-function score; about
  0.72 as a probability). The retrained run's own threshold (1.0322,
  stored in `model/metadata.json`) is NOT used for scoring — the UI
  reports the notebook's numbers.

Notebook results (the only metrics shown in the UI): **PR-AUC 0.917,
precision 0.931, recall 0.766** — 108 of 141 fake postings caught, 8
false alarms. Retrained results (see `model/METRICS.md`): PR-AUC
0.914, precision 0.939, recall 0.759 — 107 of 141 caught, 7 false
alarms.

**Risk bands** (decision-function score): high ≥ 0.949 ("High risk"),
some 0–0.949 ("Some warning signs"), few < 0 ("Few warning signs").
**Predictions are risk estimates, never a verdict** — the API and UI
both carry the disclaimer "This is a statistical estimate, not proof.
The model misses about 1 in 4 scams and can flag real postings."

**Artifact**: the app loads `model/model_artifacts.joblib`, a dict
`{"vec", "model", "meta_cols", "threshold", "feature_names"}`
exported from the notebook (see the README for the export cell).
The legacy pair (`tfidf_vectorizer.joblib` + `logreg_model.joblib`)
is kept as a fallback. Deploys do not retrain — the committed
artifact is the deployed model. `requirements.txt` pins
scikit-learn 1.9.1, the version the artifacts were trained with
(the old 1.5.2 pin did not match the training environment).

`backend/ml.py` also returns 9 rule-based indicators (upfront fee,
wire transfer, urgency language, no company profile, no
requirements, no logo, phone/email/URL tokens in text, very short
posting).

## API contract

Base: `/` (frontend at `/`, assets at `/assets/*`).

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | `{"status": "ok", "model_loaded": bool}` |
| GET | `/api/jobs` | List jobs. Params: `q` (title/company/location), `category`, `risk_band` (high/some/few), `min_risk`, `max_risk`, `sort` (newest/oldest/risk_desc/risk_asc), `page`, `per_page` (max 100). Returns `{items, total, page, per_page}`. Each item carries `decision_score` and `language`. |
| GET | `/api/jobs/{id}` | One job, 404 if missing. |
| POST | `/api/predict` | Body: title, company, description, requirements, benefits, company_profile, location, salary_range, telecommuting, has_company_logo, has_questions, has_salary. Returns decision_score, risk_band, risk_label, threshold, top_raising, top_lowering, indicators, language, language_ok, language_message, disclaimer. 400 when the total input is under 100 or over 10,000 characters. |
| POST | `/api/jobs/ingest` | Header `X-Ingest-Token: <INGEST_TOKEN>`. Runs one ingest pass. Returns `{fetched, kept, inserted, updated, duplicates, expired_marked, runs}`. 401 without the token; 503 if no token is configured. |
| GET | `/api/stats` | `{total_jobs, active_jobs, by_category, by_risk_band, last_ingest, model}` |

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
│                       ml, ingest, scheduler, language, main)
├── common/             features.py — text cleaning + metadata flags,
│                       shared by training and inference
├── train/              train_model.py — reproduces the notebook pipeline
├── frontend/           React + Vite dashboard (builds to backend/static)
├── model/              model_artifacts.joblib, metadata.json, METRICS.md
├── tests/              pytest suite (API, ingestion, model, smoke)
├── .github/workflows/  ingest.yml — 30-minute cron
├── Dockerfile          two-stage (Node build + Python runtime)
├── render.yaml         Render Blueprint (web service + Postgres)
├── requirements.txt    backend runtime deps
└── DEPLOYMENT.md / ARCHITECTURE.md / README.md
```

## Configuration

All settings are environment variables (see `.env.example`):
`DATABASE_URL`, `INGEST_TOKEN`, `MODEL_DIR`, `FRONTEND_DIR`,
`RUN_SCHEDULER`, `INGEST_INTERVAL_MINUTES`, `ARBEITNOW_MAX_PAGES`.
No secrets are committed; `INGEST_TOKEN` comes from the Render
environment (generated) and the GitHub Actions secrets.

## Privacy

Pasted text from the checker is never stored or logged: `/api/predict`
holds it only for the duration of the request, and the only logging in
the backend is request counts and ingest failures. The UI states this
next to the form. User text is rendered by React (escaped by default);
no `dangerouslySetInnerHTML` is used anywhere.

## Known limitations

- One ingestion source (Arbeitnow). Job types there are a messy
  German/English mix, so category mapping is best-effort.
- The model was trained on 2019-era English Kaggle data; German-language
  postings get no risk level (the model only works for English).
- The Arbeitnow API returns no company profile or requirements, so
  ingested listings always carry those two flags — feed scores are
  thinner than a full posting check.
- The cross-source normalised-dedupe set lives in memory per ingest run.
- The frontend fetches 20 jobs per page from the API.
- Arbeitnow's terms ask for a link back (present in the footer) and
  allow revoking API permission at any time; the use licence is not
  explicit about API data, so the feed is a non-commercial demo.
