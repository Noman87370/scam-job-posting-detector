# Deployment Guide — Scam Job Posting Detector

The platform is a single service: FastAPI backend + React frontend (built into `backend/static` and served by the backend) + Postgres/SQLite + an in-process scheduler. The service is live at https://scam-job-detector-hob9.onrender.com — these are the steps to redeploy it or to set it up again from scratch.

## Prerequisites

1. **GitHub account** — the repo must be pushed there first.
2. **Render account** (free tier) — https://render.com (Alternative: any host that runs a Docker container or a Python web service with a Postgres database — see "Docker (any host)" below.)
3. A strong value for `INGEST_TOKEN` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`).

## 1. Push to GitHub

```bash
cd ~/workspace/scam-job-detector
git add -A
git commit -m "Scam Job Detector: bilingual checker (English ML + German rule-based)"
git push origin main
```

Note: the model artifact `model/model_artifacts.joblib` (~3.4 MB) IS committed — it is the model the app loads, exported from the research notebook (see the README for the export cell). Deploys do NOT retrain: the build only installs dependencies and builds the frontend, so the deployed model is identical on every deploy. (The legacy pair `model/tfidf_vectorizer.joblib` + `model/logreg_model.joblib` is still in the repo as a fallback.)

## 2. Deploy on Render (Blueprint)

1. In the Render dashboard: **New → Blueprint**, select the GitHub repo.
2. Render reads `render.yaml` and creates:
   - **Web service** `scam-job-detector` (free plan, Python 3.12). Build command installs Python deps and builds the frontend. Start command runs `uvicorn backend.main:app`.
   - **Postgres database** `scam-jobs-db` (free plan). Its connection string is wired into `DATABASE_URL` automatically.
   - `INGEST_TOKEN` is generated automatically (`generateValue: true`) — copy it from the service's Environment page after the first deploy.
3. Wait for the first deploy to finish. Every push to `main` redeploys automatically.

On startup the app creates the tables if missing and adds the `decision_score` / `language` columns to a database created before them — no manual migration is needed. The next ingest run backfills those two fields on older rows.

## 3. Set up the scheduled ingestion (GitHub Actions)

The free web service sleeps when idle, so the in-process scheduler alone is not reliable. The workflow `.github/workflows/ingest.yml` POSTs to `/api/jobs/ingest` every 30 minutes, which also wakes the service.

In the GitHub repo: **Settings → Secrets and variables → Actions**, add two repository secrets:

| Secret | Value |
|---|---|
| `APP_URL` | The Render URL, e.g. `https://scam-job-detector-hob9.onrender.com` (no trailing slash) |
| `INGEST_TOKEN` | The exact value from the Render service's Environment page |

Then trigger it once manually: **Actions → Scheduled ingestion → Run workflow**, and confirm the run is green.

## 4. Verify

```bash
APP=https://scam-job-detector-hob9.onrender.com
curl $APP/health
# {"status":"ok","model_loaded":true}

curl -X POST $APP/api/jobs/ingest -H "X-Ingest-Token: <INGEST_TOKEN>"
# {"source":"arbeitnow","fetched":...,"kept":...,"inserted":...,"updated":...,"duplicates":...,"expired_marked":...,"error":null}

curl $APP/api/stats
# {"total_jobs":...,"active_jobs":...,"by_category":{...},"by_risk_band":{...},...}

curl -X POST $APP/api/predict -H "Content-Type: application/json" \
  -d '{"title": "Work from home, earn $5000/week", "description": "Urgent hiring, no experience needed, pay a small registration fee to start immediately and earn money fast from home."}'
# {"decision_score":...,"risk_band":"high","risk_label":"High risk","threshold":0.949,...}
```

Open `$APP` in a browser: the dashboard should list German jobs with risk badges, and the "Check a posting" form should score the fictional scam-like example as "High risk" and the normal example as "Few warning signs". If it says "No jobs yet", ingestion has not run — trigger the GitHub Actions workflow once (step 3).

## Docker (any host)

```bash
docker build -t scam-job-detector .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/scam_jobs \
  -e INGEST_TOKEN=<secret> \
  scam-job-detector
```

With Docker Compose, add a `postgres:16` service and point `DATABASE_URL` at it; the app creates its tables on startup.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set INGEST_TOKEN
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

- **Free-tier sleep:** Render's free web service spins down after 15 minutes idle; the first request after a pause takes ~30–60 s to wake.
- **Free Postgres:** Render's free Postgres database expires after 90 days. Alternatives: Neon, Supabase (free tiers), or SQLite on a persistent volume (single instance only).
- **One source:** ingestion currently uses only the Arbeitnow API. Adding a second source means a new fetcher in `backend/ingest.py`.
- **Predictions are estimates:** the model was trained on 2019-era Kaggle data; scores are risk estimates, not verdicts. The UI says so.
