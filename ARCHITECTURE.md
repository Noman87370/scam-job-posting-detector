# Architecture — Scam Job Posting Detector

## Overview

A single-service web app: a FastAPI backend serves both the REST API and
the built React frontend (static files in `backend/static`). A
background scheduler ingests fresh job postings every 30 minutes, scores
each one (English with the ML model, German with the rule-based checker),
and stores the results. A GitHub Actions cron calls the ingest endpoint
on the same schedule so the free-tier host wakes up. Visitors can also
paste an English or German posting (or a message) into a structured
form and get a risk level with an explanation. The UI is bilingual
(German/English); all UI text lives in `frontend/src/i18n.js`.

```
Arbeitnow API ──► ingest.py ──► language detect (de/en)
                                  │            │
                    ML (TF-IDF + LogisticRegression)   German rules (de_rules.py)
                                  │            │
                                  ▼            ▼
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
| German check | rule-based checker (`backend/de_rules.py`, rules in `backend/rules_de.py`) — no ML, no extra dependency |
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
   detected with langdetect and stored. `detect_language` (min 20
   chars) is used for the feed; `analyze_language` (min 100 chars,
   returns code + confidence + mixed + unsure) is used for the
   checker form. Rows ingested before the language column existed
   are backfilled on the next ingest run (language from stored text;
   decision score recovered from the stored probability via log-odds
   for English rows; German rows are re-scored with the rule checker).
4. **Score** (`backend/ingest.py::_score_listing`): English listings
   go through `backend/ml.py` (see below); German listings go
   through `backend/de_rules.py` (fraud_probability stored as 0.0 —
   not applicable — and decision_score as NULL; the rule band and
   matched rules are stored in `indicators` with
   `"method": "de"`). A scoring failure stores the row unscored
   (`"method": "unscored"`) instead of failing the whole run.
   **ML scoring** (`backend/ml.py`): the posting text is cleaned
   exactly as in training (lowercase, strip HTML, map URL/email/phone
   tokens, a-z only), vectorised with the saved TF-IDF vectorizer,
   and scored by the saved logistic regression model. The decision
   threshold is the notebook's **0.949** (decision-function score).
   Contributions are x_i * coef_i over all features; the top 5
   raising and top 3 lowering features are returned with readable
   names.
   **German scoring** (`backend/de_rules.py`): case-insensitive
   regexes from `backend/rules_de.py` run over the sentences of the
   text; each rule has id, category, severity (critical / strong /
   mild), a plain-language explanation in German and English, and
   the matched sentence is kept as evidence. A critical rule is
   downgraded to mild when its sentence contains a legit-context
   marker (job duty / right-to-work check). Banding: any critical
   → high; else 2+ strong, or strong + mild totalling a weight of
   3+ → some; else few. No ML metrics exist for this path. Patterns
   stay narrow on purpose: the identity-check rule matches only the
   noun "Identitätsprüfung" — a bare verb stem ("identifizier*")
   flagged ordinary duty wording and put all 58 High-risk feed rows
   on one false rule (fixed 2026-11-26; regression tests in
   `tests/test_de_rules.py` hold the real sentences). The rule set
   carries a version (`RULES_VERSION`, stored in each German row's
   indicators); the backfill re-scores rows whose stored version
   differs, so a rule fix heals the live feed on the next ingest.
5. **Store** (`backend/models.py`): dedupe on `(source, external_id)`
   and on normalised `(title, company, location)`; update re-seen
   postings in place. Expiry: `posted_at` older than 60 days, or not
   seen in the latest full ingest + 7 days grace — marked `expired`,
   never deleted. A startup migration (`ensure_job_columns`) adds the
   `decision_score` / `language` columns to databases created before
   them.
6. **Serve**: the API returns stored jobs; the dashboard filters/sorts
   them from the API. The paste-in form (`POST /api/predict`) accepts
   the structured fields plus `posting_language` (`auto` / `de` /
   `en`) and `context_flags` (German only), enforces 100–10,000
   characters in total, and returns `path` (`ml` / `de` /
   `needs_choice` / `unsupported`): an ML result (decision score,
   risk band, feature contributions, indicators) or a German rule
   result (band, matched rules with evidence sentences, counts,
   advice flag) — never a probability as a "% chance of scam".
   An explicit posting-language choice always wins over detection.

## Language routing (checker form)

`POST /api/predict` routes on `posting_language`:

- `auto` → `analyze_language` on the merged text (≥100 chars).
  Mixed German+English (second language prob ≥ 0.20) or unsure
  (top prob < 0.5, too short, or detection failure) → `path`
  `needs_choice`, no risk level, the UI asks the user to choose.
  A detected language that is neither de nor en → `unsupported`.
  `de` → German rule check; `en` → ML path.
- `de` / `en` → the matching path directly, whatever the text
  looks like; the response still carries `detected_language` /
  `detected_confidence` so the UI can note a mismatch.

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
| POST | `/api/predict` | Body: title, company, description, requirements, benefits, company_profile, location, salary_range, telecommuting, has_company_logo, has_questions, has_salary, plus `posting_language` (`auto`/`de`/`en`, default `auto`) and `context_flags` (German only). Returns `path` (`ml`/`de`/`needs_choice`/`unsupported`), `detected_language`, `detected_confidence`, `mixed`; ML path: decision_score, risk_band, risk_label, threshold, top_raising, top_lowering, indicators, method_label_de/en, disclaimer_de; German path: de_band, de_band_label_de/en, de_critical/de_strong/de_mild, de_matched (rule_id, category, severity, explanation_de/en, evidence, downgraded), de_checkboxes, de_advice, de_advice_link, de_few_note_de/en. 400 when the total input is under 100 or over 10,000 characters, or `posting_language` is invalid. |
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
│                       ml, ingest, scheduler, language, de_rules,
│                       rules_de, main)
├── common/             features.py — text cleaning + metadata flags,
│                       shared by training and inference
├── train/              train_model.py — reproduces the notebook pipeline
├── frontend/           React + Vite dashboard (builds to backend/static)
│                       src/i18n.js — all UI text, key -> {de, en}
├── model/              model_artifacts.joblib, metadata.json, METRICS.md
├── tests/              pytest suite (API, ingestion, model, smoke,
│                       German rule cases + German API + German feed)
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
no `dangerouslySetInnerHTML` is used anywhere. The German checker
returns matched sentences as evidence — the backend returns them
verbatim and React escapes them on display (asserted in tests).

## Known limitations

- One ingestion source (Arbeitnow). Job types there are a messy
  German/English mix, so category mapping is best-effort.
- The model was trained on 2019-era English Kaggle data; German-language
  postings are checked with the rule-based checker, which has no
  labelled validation data (only a synthetic sanity check on 40
  invented texts).
- The Arbeitnow API returns no company profile or requirements, so
  ingested listings always carry those two flags — feed scores are
  thinner than a full posting check.
- The cross-source normalised-dedupe set lives in memory per ingest run.
- The frontend fetches 20 jobs per page from the API.
- Arbeitnow's terms ask for a link back (present in the footer) and
  allow revoking API permission at any time; the use licence is not
  explicit about API data, so the feed is a non-commercial demo.
