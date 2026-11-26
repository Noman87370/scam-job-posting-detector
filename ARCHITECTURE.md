# Architecture — Scam Job Posting Detector

## Overview

A single-service web app with no database: a FastAPI backend serves both the REST API and the built React frontend (static files in `backend/static`). The backend fetches live job listings from Arbeitnow server-side on demand and holds them in an in-memory cache. Visitors can paste an English or German posting into a structured form and get a risk level with an explanation. Listings carry no risk labels; scoring happens only for pasted text. The UI is bilingual (German/English); all UI text lives in `frontend/src/i18n.js`.

```
Arbeitnow API ──► in-memory cache (10-min TTL) ──► FastAPI (main.py) ──► React dashboard
                                                              │
POST /api/predict ──► language detect (de/en) ──► ML (TF-IDF + LogisticRegression)
                                                 └─► German rules (de_rules.py)
```

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12.3), Uvicorn |
| Frontend | React 19 + Vite 8, plain CSS, no component library |
| ML | scikit-learn (TF-IDF + LogisticRegression), joblib artifacts, langdetect |
| German check | rule-based checker (`backend/de_rules.py`, rules in `backend/rules_de.py`) — no ML, no extra dependency |
| Feed | Arbeitnow public API, fetched server-side, in-memory cache (no database) |
| Hosting | Render free web service, 512 MB RAM (see DEPLOYMENT.md) |
| Tests | pytest + FastAPI TestClient |

## Data flow

1. **Fetch** (on demand): when a visitor opens the listings, the backend fetches from `https://www.arbeitnow.com/api/job-board-api` (free public API, no key, updated hourly), at most 3 pages, with a 10 s timeout. Each posting is mapped to the listing shape: HTML stripped, job type mapped to a category. The Arbeitnow API returns no company profile or requirements.
2. **Germany filter**: keep a posting if its location is in Germany or it is remote with no non-German location. A German-city list (Berlin, München, Hamburg, …) plus the words "Germany"/"Deutschland" decide this.
3. **Cache**: the fetched listings are held in memory with a 10-minute TTL. Responses carry `stale` and `cached_at` so the UI can show when the data was fetched and whether it is stale. If the upstream fetch fails, the backend serves the last cached copy and marks it stale; if there is no cached copy, the API returns HTTP 503 with a plain message and the UI shows an error state with a retry button.
4. **Serve**: `GET /api/jobs` filters (search text, category) and sorts (newest/oldest) the cached listings in memory and paginates them. No listing is scored and no risk label is stored or returned.
5. **Check a posting** (`POST /api/predict`): accepts the structured fields plus `posting_language` (`auto` / `de` / `en`) and `context_flags` (German only), enforces 100–10,000 characters in total, and returns `path` (`ml` / `de` / `needs_choice` / `unsupported`): an ML result (decision score, risk band, feature contributions, indicators) or a German rule result (band, matched rules with evidence sentences, counts, advice flag) — never a probability as a "% chance of scam". An explicit posting-language choice always wins over detection. Pasted text is held only for the duration of the request and is never stored.

## Language routing (checker form)

`POST /api/predict` routes on `posting_language`:

- `auto` → `analyze_language` on the merged text (≥100 chars). Mixed German+English (second language prob ≥ 0.20) or unsure (top prob < 0.5, too short, or detection failure) → `path` `needs_choice`, no risk level, the UI asks the user to choose. A detected language that is neither de nor en → `unsupported`. `de` → German rule check; `en` → ML path.
- `de` / `en` → the matching path directly, whatever the text looks like; the response still carries `detected_language` / `detected_confidence` so the UI can note a mismatch.

## Model

Trained from the Kaggle "Real / Fake Job Posting Prediction" dataset (17,880 postings, 18 columns, 806 fake in the raw data) by `train/train_model.py`, reproducing the research notebook:

- Text = title + company_profile + description + requirements + benefits, cleaned as above; duplicates/empties dropped before splitting (15,691 left, 707 fake; 12,552 train / 3,139 test, stratified, seed 42).
- Features: TF-IDF 1–2 grams (min_df=3, max_df=0.9, English stop words, sublinear, max 60k) + 10 metadata flags.
- Model: `LogisticRegression(C=5, class_weight="balanced", max_iter=1000)` — the LinearSVC compared in the notebook (PR-AUC 0.923 vs 0.917 for LogReg) is not used. Verified loaded: LogisticRegression, coef_ shape (1, 60010).
- Threshold: the notebook's 0.949 (decision-function score; about 0.72 as a probability). The retrained run's own threshold (1.0322, stored in `model/metadata.json`) is NOT used for scoring — the UI reports the notebook's numbers.

Notebook results (the only metrics shown in the UI): **PR-AUC 0.917, precision 0.931, recall 0.766** — 108 of 141 fake postings caught, 8 false alarms. Confusion matrix: actual real 2,990 / 8; actual fake 33 / 108. Retrained results (see `model/METRICS.md`): PR-AUC 0.914, precision 0.939, recall 0.759 — 107 of 141 caught, 7 false alarms.

**Risk bands** (decision-function score, checker only): high ≥ 0.949 ("High risk"), some 0–0.949 ("Some warning signs"), few < 0 ("Few warning signs"). **Predictions are risk estimates, never a verdict** — the API and UI both carry the disclaimer "This is a statistical estimate, not proof. The model misses about 1 in 4 scams and can flag real postings."

**Artifact**: the app loads `model/model_artifacts.joblib`, a dict `{"vec", "model", "meta_cols", "threshold", "feature_names"}` exported from the notebook (see the README for the export cell). The legacy pair (`tfidf_vectorizer.joblib` + `logreg_model.joblib`) is kept as a fallback. Deploys do not retrain — the committed artifact is the deployed model. `requirements.txt` pins scikit-learn 1.9.1, the version the artifacts were trained with.

`backend/ml.py` also returns 9 rule-based indicators (upfront fee, wire transfer, urgency language, no company profile, no requirements, no logo, phone/email/URL tokens in text, very short posting).

## German checker

Rule-based, not ML (`backend/de_rules.py`, rules in `backend/rules_de.py`): case-insensitive regexes over the sentences of the text, handling umlaut spellings (ä/ae, ö/oe, ü/ue, ß/ss) and variants such as Video-Ident / Videoident / Video Ident; each matched rule returns its sentence as evidence. Critical rules (identity verification, bank-account opening/testing, money or parcel forwarding, payment upfront) give "High risk"; a critical rule is downgraded to mild when its sentence clearly describes a job duty or a legitimate right-to-work check. Strong rules (weight 2: easy-money claims, task-scam wording, messenger-only contact, instant acceptance) and mild rules (weight 1: free-mail contact, no company details, three or more exclamation marks) combine into "Some warning signs" (2+ strong, or 1 strong with total weight ≥ 3) or "Few warning signs found". Patterns stay narrow on purpose: the identity-check rule matches only the noun "Identitätsprüfung" — a bare verb stem flagged ordinary duty wording (fixed 2026-11-26; see `CHANGELOG.md`). No ML metrics exist for this path; it is not validated on labelled data (see the README).

## API contract

Base: `/` (frontend at `/`, assets at `/assets/*`).

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | `{"status": "ok", "model_loaded": bool}` |
| GET | `/api/jobs` | List jobs from the in-memory cache. Params: `q` (title/company/location), `category`, `sort` (`newest` / `oldest`), `page`, `per_page`. Returns `{total, page, per_page, items, stale, cached_at}`. Each item: `{id, source, external_id, title, company, location, url, description, category, posted_at}`. No risk fields. |
| GET | `/api/jobs/{job_id}` | One job, 404 if missing. |
| POST | `/api/predict` | Body: title, company, description, requirements, benefits, company_profile, location, salary_range, telecommuting, has_company_logo, has_questions, has_salary, plus `posting_language` (`auto`/`de`/`en`, default `auto`) and `context_flags` (German only). Returns `path` (`ml`/`de`/`needs_choice`/`unsupported`), `detected_language`, `detected_confidence`, `mixed`; ML path: decision_score, risk_band, risk_label, threshold, top_raising, top_lowering, indicators, method_label_de/en, disclaimer_de; German path: de_band, de_band_label_de/en, de_critical/de_strong/de_mild, de_matched (rule_id, category, severity, explanation_de/en, evidence, downgraded), de_checkboxes, de_advice, de_advice_link, de_few_note_de/en. 400 when the total input is under 100 or over 10,000 characters, or `posting_language` is invalid; 503 if the model is unavailable. |
| GET | `/api/stats` | `{total_jobs, active_jobs, by_category, model, feed: {source: "arbeitnow", cached_at, cache_age_seconds, upstream_ok, stale}}` |

There is no ingestion endpoint and no write endpoint for jobs. `GET /api/jobs` and `GET /api/stats` read only the in-memory cache.

## Cache behaviour

- TTL 10 minutes; upstream timeout 10 s; at most 3 pages fetched per refresh.
- A refresh is triggered by a request when the cache is older than the TTL; concurrent requests during a refresh share one fetch.
- `stale: true` means the response comes from a cache older than the TTL because the upstream fetch failed. `cached_at` is when the cached copy was fetched; `cache_age_seconds` (in `/api/stats`) is its age at response time.
- The cache lives only in the web service process: a restart or a new deploy starts with an empty cache, and the first listings request fetches from Arbeitnow. Nothing is persisted.

## No database

There is no database in this design: no Postgres, no SQLite, no `DATABASE_URL`, no migrations, no stored jobs, and no stored scores. The previous version used a free Render Postgres database (which expired after 30 days) with an ingestion endpoint, an in-process scheduler and a GitHub Actions cron; all of that was removed in the 2026-11-26 final round (see `CHANGELOG.md`). Removing persistence also removes the failure mode where a rule fix left already-stored rows wrong.

## Project layout

```
scam-job-detector/
├── backend/            FastAPI app (config, ml, language, de_rules,
│                       rules_de, arbeitnow fetch + cache, main)
├── common/             features.py — text cleaning + metadata flags,
│                       shared by training and inference
├── train/              train_model.py — reproduces the notebook pipeline
├── frontend/           React + Vite dashboard (builds to backend/static)
│                       src/i18n.js — all UI text, key -> {de, en}
├── model/              model_artifacts.joblib, metadata.json, METRICS.md
├── tests/              pytest suite (API, model, smoke,
│                       German rule cases + German API)
├── .github/workflows/  ci.yml — pytest on every push and pull request
├── Dockerfile          two-stage (Node build + Python runtime)
├── render.yaml         Render Blueprint (web service only)
├── requirements.txt    backend runtime deps
└── DEPLOYMENT.md / ARCHITECTURE.md / README.md / CHANGELOG.md
```

## Configuration

No secrets are required. Optional environment variables: `MODEL_DIR` (default `./model`), `FRONTEND_DIR` (default `./backend/static`), `ARBEITNOW_MAX_PAGES` (default `3`), `FEED_CACHE_TTL_SECONDS` (default `600`). No secrets are committed.

## Privacy

Pasted text from the checker is never stored or logged: `/api/predict` holds it only for the duration of the request, and the backend logs no posting content. The UI states this next to the form. User text is rendered by React (escaped by default); no `dangerouslySetInnerHTML` is used anywhere. The German checker returns matched sentences as evidence — the backend returns them verbatim and React escapes them on display (asserted in tests).

## Known limitations

- One listing source (Arbeitnow). Job types there are a messy German/English mix, so category mapping is best-effort.
- The model was trained on an older public dataset; German-language postings are checked with the rule-based checker, which has no labelled validation data (only a synthetic sanity check on 40 invented texts).
- The Arbeitnow API returns no company profile or requirements, so a listing checked with "Check this posting" is scored without those two fields — thinner than a full posting check.
- The in-memory cache is per process: a restart clears it, and the free tier has a single instance.
- The frontend fetches 20 jobs per page from the API.
- Arbeitnow's terms ask for a link back (present in the footer) and allow revoking API permission at any time; the use licence is not explicit about API data, so the feed is a non-commercial demo.
