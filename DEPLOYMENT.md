# Deployment Guide — Scam Job Posting Detector

The platform is a single service: FastAPI backend + React frontend (built
into `backend/static` and served by the backend) + Postgres/SQLite + an
in-process scheduler. Nothing here has been deployed yet — these are the
exact steps to do it once accounts exist.

## Prerequisites

1. **GitHub account** — the repo must be pushed there first.
2. **Render account** (free tier) — https://render.com
   (Alternative: any host that runs a Docker container or a Python web
   service with a Postgres database — see "Docker (any host)" below.)
3. A strong value for `INGEST_TOKEN` (generate with
   `python -c "import secrets; print(secrets.token_hex(32))"`).

## 1. Push to GitHub

```bash
cd ~/workspace/scam-job-detector
git init          # if not already a repo
git add .
git commit -m "Scam Job Detector platform: API, ingestion, React frontend"
git branch -M main
git remote add origin https://github.com/Noman87370/scam-job-posting-detector.git
git push -u origin main
```

Note: the retrained model artifacts in `model/` (~3 MB, binary `.joblib`
files) are NOT committed — they are trained at build time instead (the
Dockerfile's train stage, or the `python train/train_model.py` step in
the Render build command). Training downloads the public Kaggle dataset
via kagglehub and reproduces the notebook pipeline exactly; see
`model/METRICS.md` for the measured metrics.

## 2. Deploy on Render (Blueprint, ~5 minutes)

1. In the Render dashboard: **New → Blueprint**, select the GitHub repo.
2. Render reads `render.yaml` and creates:
   - **Web service** `scam-job-detector` (free plan, Python 3.12).
     Build command installs Python deps, trains the model from the
     public Kaggle dataset, then builds the frontend.
     Start command runs `uvicorn backend.main:app`.
   - **Postgres database** `scam-jobs-db` (free plan). Its connection
     string is wired into `DATABASE_URL` automatically.
   - `INGEST_TOKEN` is generated automatically (`generateValue: true`) —
     copy it from the service's Environment page after the first deploy.
3. Wait for the first deploy to finish (about 3–5 minutes).

## 3. Set up the scheduled ingestion (GitHub Actions)

The free web service sleeps when idle, so the in-process scheduler alone
is not reliable. The workflow `.github/workflows/ingest.yml` POSTs to
`/api/jobs/ingest` every 30 minutes, which also wakes the service.

In the GitHub repo: **Settings → Secrets and variables → Actions**,
add two repository secrets:

| Secret | Value |
|---|---|
| `APP_URL` | The Render URL, e.g. `https://scam-job-detector.onrender.com` (no trailing slash) |
| `INGEST_TOKEN` | The exact value from the Render service's Environment page |

Then trigger it once manually: **Actions → Scheduled ingestion → Run
workflow**, and confirm the run is green.

## 4. Verify

```bash
APP=https://scam-job-detector.onrender.com
curl $APP/health
# {"status":"ok","model_loaded":true}

curl -X POST $APP/api/jobs/ingest -H "X-Ingest-Token: <INGEST_TOKEN>"
# {"fetched":...,"kept":...,"inserted":...,"updated":...,"duplicates":...,"expired_marked":...}

curl $APP/api/stats
# {"total_jobs":...,"active_jobs":...,"by_category":{...},"by_risk_band":{...},...}
```

Open `$APP` in a browser: the dashboard should list German jobs with
fraud-probability meters. If it says "No jobs yet", ingestion has not run
— trigger the GitHub Actions workflow once (step 3).

## Docker (any host)

```bash
docker build -t scam-job-detector .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/scam_jobs \
  -e INGEST_TOKEN=<secret> \
  scam-job-detector
```

With Docker Compose, add a `postgres:16` service and point `DATABASE_URL`
at it; the app creates its tables on startup.

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
```

Retraining needs the Kaggle dataset (fetched via kagglehub; see
`train/train_model.py`). After retraining, restart the service — the
model is loaded lazily on first use and cached in memory.

## Known limitations

- **Free-tier sleep:** Render's free web service spins down after
  inactivity; the first request after a pause takes ~30–60 s to wake.
- **Free Postgres:** Render's free Postgres plan has a storage limit and
  may expire — check the current free-tier terms before relying on it.
  Alternatives: Neon, Supabase (free tiers), or SQLite on a persistent
  volume (single instance only).
- **One source:** ingestion currently uses only the Arbeitnow API.
  Adding a second source means a new fetcher in `backend/ingest.py`.
- **Predictions are estimates:** the model was trained on 2019-era
  Kaggle data; scores are risk estimates, not verdicts. The UI says so.
