# Scam Job Posting Detector (English postings)

Detects fraudulent job postings from text and metadata — a demo of an NLP model trained in a Kaggle notebook, with a live job feed scored by the same model.

## Live Demo

Try it at https://scam-job-detector-hob9.onrender.com — paste an English job posting (title, description, requirements and the rest) into the "Check a posting" form, or browse the live German listings. The demo runs on Render's free tier, so the first load after a pause can take up to a minute to wake up. The model only works for English postings, and it misses about 1 in 4 scams, so treat every result as a rough estimate, not a verdict.

## What it does

- **Check a posting** — fill in the fields of an English job ad (title, company profile, description, requirements, benefits, plus four checkboxes) and get a risk level with an explanation. Two fictional examples can be loaded with one click. Text you enter is processed only to compute the result and is not stored.
- **Live job listings** — real German job postings from the Arbeitnow API, refreshed every 30 minutes. Search by title, company or location; filter by category (Werkstudent, Internship, Part-time, Full-time) and risk level; sort by date or risk. Each listing links to the original posting.
- **Risk levels, never a verdict** — "High risk", "Some warning signs" or "Few warning signs", from the model's decision score. No band says "safe" or "not a scam", and no probability is shown as a "% chance of scam" (the probabilities are not calibrated).
- **Scores are risk estimates, never a verdict** — and the model was trained on English-language data, so non-English postings get no risk level at all, only the note that the result would be unreliable.

## How detection works

TF-IDF (1–2 grams, 60k features) plus 10 metadata flags, fed into a Logistic Regression classifier (`C=5`, class-balanced). Before scoring, real URLs, email addresses and phone numbers in the input are converted to the placeholders the training data used (`#URL_x#`, `#EMAIL_x#`, `#PHONE_x#`), so the token features behave as in training.

The decision rule is the notebook's: score = `model.decision_function(X)`; "High risk" starts at a score of **0.949** (a predicted probability of about 0.72). "Some warning signs" is 0 to 0.949, "Few warning signs" below 0.

Reported results on the English test set (3,139 postings, 141 fake):

| PR-AUC | Precision | Recall | Fake caught | False alarms |
|---|---|---|---|---|
| 0.917 | 93.1% | 76.6% | 108 of 141 | 8 of 2,998 real |

The loaded model is the logistic regression from the notebook (the LinearSVC that was also compared is not used). The retrained model's own measurements (PR-AUC 0.914, precision 93.9%, recall 75.9%) are recorded in `model/METRICS.md` only — the UI shows the notebook's numbers above.

## Dataset

[Real / Fake Job Posting Prediction (Kaggle)](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction): 17,880 postings, 15,691 after removing duplicates and empty texts (12,552 train / 3,139 test, stratified split). The data is not included in this repository. The original research notebook is `scam-job-posting-detector.ipynb`.

## Export the model from the notebook

After training in the notebook, export the artifacts the app loads, and print the scikit-learn version (the `requirements.txt` pin must match it — a mismatch breaks loading the pickled model):

```python
joblib.dump({"vec": vec, "model": best, "meta_cols": meta_cols, "threshold": float(t),
             "feature_names": feature_names}, "model_artifacts.joblib")
print("scikit-learn version:", sklearn.__version__)
```

Here `t` is the tuned decision threshold (0.949 in the notebook), `vec` the fitted `TfidfVectorizer`, `best` the fitted logistic regression, `meta_cols` the 10 metadata column names in order, and `feature_names = list(vec.get_feature_names_out()) + meta_cols`. Copy the resulting `model_artifacts.joblib` to `model/` and commit it — the app loads it directly, and deploys do not retrain.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy (SQLite locally, PostgreSQL in production), APScheduler
- **Frontend:** React 19 + Vite (build served by the backend)
- **ML:** scikit-learn, TF-IDF + Logistic Regression, joblib artifacts, langdetect
- **Ingestion:** Arbeitnow API, GitHub Actions cron (every 30 min)
- **Hosting:** Render (free tier) + free PostgreSQL

## Project structure

```
├── scam-job-posting-detector.ipynb   # original research notebook
├── backend/          # FastAPI app: API, ingestion, scheduler, ML serving, language check
├── common/           # shared text-cleaning / metadata features
├── train/            # train_model.py — reproduces the notebook pipeline
├── frontend/         # React + Vite dashboard (builds to backend/static)
├── model/            # model_artifacts.joblib + METRICS.md (+ legacy artifacts)
├── tests/            # pytest suite (24 tests, incl. smoke test)
├── .github/workflows/ingest.yml     # 30-minute ingestion cron
├── Dockerfile        # two-stage build (Node + Python)
├── render.yaml       # Render Blueprint (web service + Postgres)
├── requirements.txt  # backend runtime dependencies
├── DEPLOYMENT.md     # exact deploy steps
├── ARCHITECTURE.md   # stack, data flow, model, API contract
└── README.md
```

## Run locally

**Platform:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set INGEST_TOKEN
uvicorn backend.main:app --reload --port 8000
# open http://localhost:8000
```

Frontend development (optional — the backend serves the production build from `backend/static`):

```bash
cd frontend && npm install && npm run dev
```

**Research notebook:**

```bash
pip install pandas matplotlib seaborn jupyter
# download fake_job_postings.csv from Kaggle, then:
jupyter notebook scam-job-posting-detector.ipynb
```

**Retrain the model:**

```bash
pip install -r train/requirements.txt
python train/train_model.py   # writes artifacts to model/, incl. model_artifacts.joblib
```

**Tests:**

```bash
.venv/bin/python -m pytest tests/ -v
```

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Status + whether the model loaded |
| GET | `/api/jobs` | List jobs (`q`, `category`, `risk_band`, `min_risk`, `max_risk`, `sort`, `page`, `per_page`) |
| GET | `/api/jobs/{id}` | One job |
| POST | `/api/predict` | Score a pasted posting: decision score, risk band, top raising/lowering features, indicators, language check (100–10,000 characters total) |
| POST | `/api/jobs/ingest` | Trigger ingestion (header `X-Ingest-Token`) |
| GET | `/api/stats` | Totals by category and risk band |

Example:

```bash
curl -X POST https://scam-job-detector-hob9.onrender.com/api/predict \
  -H "Content-Type: application/json" \
  -d '{"title": "Work from home, earn $5000/week", "description": "Urgent hiring, no experience needed, pay a small registration fee to start immediately and earn money fast from home."}'
```

## Deployment

See `DEPLOYMENT.md` for the exact steps. In short: Render Blueprint (`render.yaml`) creates the web service + PostgreSQL, and the GitHub Actions workflow (`.github/workflows/ingest.yml`) triggers ingestion every 30 minutes. The workflow needs two repository secrets (Settings → Secrets and variables → Actions):

- `APP_URL` — the live service URL, e.g. `https://scam-job-detector-hob9.onrender.com` (no trailing slash)
- `INGEST_TOKEN` — must match the `INGEST_TOKEN` env var of the Render web service

Note: the free Render service sleeps after 15 minutes idle (cold start ~60 s), so the in-app scheduler alone cannot keep the feed fresh — the GitHub Actions cron is what keeps it updated, and it also wakes the service.

## Job listings source

Listings come from the [Arbeitnow](https://www.arbeitnow.com) free public job-board API (`https://www.arbeitnow.com/api/job-board-api`, no key required). Its terms ask for a link back to Arbeitnow.com and for no abuse; the site's terms of service also say API permission can be revoked at any time, and the use licence (personal, non-commercial) is not explicit about whether it covers API data — so this feed is a non-commercial demo, and the feed should be removed if Arbeitnow objects. Ingestion is cached (one fetch every 30 minutes, ~10 requests per run) rather than re-reading the feed per visitor.

## Key insights

- Both linear models perform almost identically on PR-AUC, so the main gains come from handling class imbalance and choosing the decision threshold, not from the model type.
- The model flagged 116 of 3,139 test postings (3.7%); 108 of them were fake, so about 9 in 10 alerts are real scams — but about 1 in 4 scams is still missed.
- Removing duplicate or empty postings before the split prevents identical texts from appearing in both training and test data.

## Limitations

- Only about 800 fake examples in total (141 in the test set), from a single dataset, so the metrics carry uncertainty; scam wording also changes over time.
- The threshold favors precision, which means roughly one in four scams is missed. A platform that prefers recall would choose a lower threshold.
- Text features alone cannot catch carefully written scams.
- Results come from one train/test split, with no external validation set.
- English only: the model was trained on English postings. German listings in the feed are shown without a risk level.
- The Arbeitnow API does not return a company profile or requirements, so every ingested listing is scored with those two flags set — the feed scores are thinner than a full posting check.

## Future improvements

- Sentence-embedding features (e.g. MiniLM) compared with TF-IDF.
- Cost-based threshold (cost of a missed scam vs. cost of a false alarm).
- More job sources beyond Arbeitnow.

## Kurzfassung (Deutsch)

Dieses Projekt erkennt betrügerische Stellenanzeigen mit TF-IDF und logistischer Regression. Da nur etwa 4,8 % der Anzeigen gefälscht sind, wird nicht mit der Accuracy, sondern mit PR-AUC, Recall und Precision bewertet. Beim gewählten Schwellenwert erkennt das Modell etwa 77 % der betrügerischen Anzeigen bei einer Precision von 93 %. Die Live-Plattform zeigt echte deutsche Stellenanzeigen und ein Formular, in das man eine englische Stellenanzeige einfügen und prüfen kann: https://scam-job-detector-hob9.onrender.com

## Contact

**Abdullah Al Noman** · M.Sc. Medical Engineering (Medical Robotics), FAU Erlangen-Nürnberg
[GitHub](https://github.com/Noman87370)
