# Deployment Guide — Scam Job Posting Detector

The platform is a single service: FastAPI backend + React frontend (built into `backend/static` and served by the backend), with no database. The service is live at https://scam-job-detector-hob9.onrender.com — these are the steps to redeploy it or to set it up again from scratch.

## Prerequisites

1. **GitHub account** — the repo must be pushed there first.
2. **Render account** (free tier) — https://render.com (Alternative: any host that runs a Docker container or a Python web service — see "Docker (any host)" below.)

No secrets are required. There are no repository secrets to set up: the `APP_URL` and `INGEST_TOKEN` secrets and the GitHub Actions ingest workflow (`.github/workflows/ingest.yml`) from the previous version were removed together with the ingestion endpoint and the database. Do not recreate them.

## 1. Push to GitHub

```bash
cd "C:\Users\Abdullah Al Noman\scam-job-posting-detector"
git add -A
git commit -m "Scam Job Detector: no-database design (Option S)"
git push origin main
```

Note: the model artifact `model/model_artifacts.joblib` (~3.4 MB) IS committed — it is the model the app loads, exported from the research notebook (see the README for the export cell). Deploys do NOT retrain: the build only installs dependencies and builds the frontend, so the deployed model is identical on every deploy. (The legacy pair `model/tfidf_vectorizer.joblib` + `model/logreg_model.joblib` is still in the repo as a fallback.)

## 2. Deploy on Render (Blueprint)

1. In the Render dashboard: **New → Blueprint**, select the GitHub repo.
2. Render reads `render.yaml` and creates a single **web service** `scam-job-detector` (free plan, Python 3.12.3). Build command installs Python deps and builds the frontend. Start command runs `uvicorn backend.main:app`. No database is created.
3. Wait for the first deploy to finish. Every push to `main` redeploys automatically. `render.yaml` in this repo is web-service-only: no database, no `INGEST_TOKEN`, no scheduler settings.

On startup the app loads the committed model artifact into memory. The feed cache starts empty and is filled on the first listings request from the Arbeitnow API.

## 3. Verify

```bash
APP=https://scam-job-detector-hob9.onrender.com
curl $APP/health
# {"status":"ok","model_loaded":true}

curl "$APP/api/jobs?per_page=5"
# {"total":...,"page":1,"per_page":5,"items":[...],"stale":false,"cached_at":"..."}

curl $APP/api/stats
# {"total_jobs":...,"active_jobs":...,"by_category":{...},"model":{...},"feed":{"source":"arbeitnow","cached_at":"...","cache_age_seconds":...,"upstream_ok":true,"stale":false}}

curl -X POST $APP/api/predict -H "Content-Type: application/json" \
  -d '{"title": "Work from home, earn $5000/week", "description": "Urgent hiring, no experience needed, pay a small registration fee to start immediately and earn money fast from home."}'
# {"decision_score":...,"risk_band":"high","risk_label":"High risk","threshold":0.949,...}
```

Open `$APP` in a browser: the dashboard should list German jobs (without risk labels), and the "Check a posting" form should score the fictional scam-like example as "High risk" and the normal example as "Few warning signs". If it shows "No job listings found" with no search or filter active, the Arbeitnow fetch failed — check that the service can reach `https://www.arbeitnow.com/api/job-board-api` and retry; there is no ingest workflow to trigger.

## Docker (any host)

```bash
docker build -t scam-job-detector .
docker run -p 8000:8000 scam-job-detector
```

No environment variables or secrets are needed. Optional: `-e MODEL_DIR=/app/model` and `-e FRONTEND_DIR=/app/backend/static` if the artifact or frontend build lives elsewhere in the image.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
# Frontend dev server (optional): cd frontend && npm install && npm run dev
```

## Retraining the model

```bash
pip install -r train/requirements.txt
python train/train_model.py
# writes model/*.joblib + model/metadata.json and updates model/METRICS.md
# (incl. model_artifacts.joblib, the file the app loads)
```

Retraining needs the Kaggle dataset (fetched via kagglehub if it is not under `/kaggle/input`; see `train/train_model.py`). After retraining, commit the new `model/model_artifacts.joblib` and push — the next deploy picks it up. Restart is not needed beyond the deploy; the model is loaded lazily on first use and cached in memory. Note the retrained run's threshold will differ from the notebook's 0.949 — the app uses the threshold stored in the artifact, so check it before deploying a retrained model.

## Known limitations

- **Free-tier sleep:** Render's free web service spins down after 15 minutes idle; the first request after a pause takes ~30–60 s to wake. There is no cron or scheduler keeping it awake, so the first visitor after a pause waits for the cold start, and the first listings request also fetches from Arbeitnow.
- **Free tier memory:** 512 MB RAM. The TF-IDF model and the in-memory feed cache share it; sentence-embedding models do not fit alongside the current stack on this plan.
- **No persistence:** a restart or redeploy clears the in-memory feed cache. Nothing is lost permanently — listings are re-fetched from Arbeitnow on the next request.
- **One source:** listings currently come only from the Arbeitnow API. Adding a second source means a new fetcher in the backend.
- **Predictions are estimates:** the model was trained on an older public dataset; scores are risk estimates, not verdicts. The UI says so.
- **History note:** the previous version used a free Render Postgres database, which expired after 30 days. The database has been removed entirely; there is nothing to expire now.
