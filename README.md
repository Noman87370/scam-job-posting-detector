# Scam Job Posting Detector

[![Open in Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](YOUR_KAGGLE_NOTEBOOK_LINK)

> Detects fraudulent job postings from text and metadata, with evaluation designed for rare-event data.
> **At the chosen threshold, the model catches 77% of fake postings (108 of 141) at 93% precision (PR-AUC: 0.917).**

## Problem Statement
Fake job ads (advance-fee scams, data harvesting) harm job seekers, and platforms need automated screening.
Only about 4.8% of postings in the raw dataset are fake, so accuracy is misleading: a model that always
predicts "real" already scores about 95%. This project therefore evaluates with PR-AUC, precision and recall
on the fake class, and an explicit decision threshold.

## Dataset
[Real / Fake Job Posting Prediction (Kaggle)](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction):
17,880 postings with 18 columns (free text plus metadata). After removing 2,189 duplicate and empty texts: 15,691 postings
(12,552 for training, 3,139 for testing, stratified split). The data is not included in this repository.

## Technologies Used

**Language and environment**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Jupyter](https://img.shields.io/badge/Jupyter-F37626?style=for-the-badge&logo=jupyter&logoColor=white)
![Kaggle](https://img.shields.io/badge/Kaggle-20BEFF?style=for-the-badge&logo=kaggle&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)

**Libraries**

![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-8CAAE6?style=for-the-badge&logo=scipy&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-11557C?style=for-the-badge)
![Seaborn](https://img.shields.io/badge/Seaborn-4C72B0?style=for-the-badge)

**Models and techniques**

![TF-IDF](https://img.shields.io/badge/TF--IDF-2E7D32?style=flat-square)
![Logistic Regression](https://img.shields.io/badge/Logistic_Regression-2E7D32?style=flat-square)
![LinearSVC](https://img.shields.io/badge/LinearSVC-2E7D32?style=flat-square)
![Class Weighting](https://img.shields.io/badge/Class_Weighting-455A64?style=flat-square)
![Threshold Tuning](https://img.shields.io/badge/Threshold_Tuning-455A64?style=flat-square)
![Cross-Validation](https://img.shields.io/badge/Cross--Validation-455A64?style=flat-square)
![PR-AUC](https://img.shields.io/badge/PR--AUC_Evaluation-455A64?style=flat-square)
![Error Analysis](https://img.shields.io/badge/Error_Analysis-455A64?style=flat-square)

## Approach
1. Merged title, company profile, description, requirements and benefits into one text field.
2. Cleaned the text (HTML tags, placeholder tokens for URLs, emails and phone numbers) and removed duplicates **before** splitting, to avoid train/test leakage.
3. Features: TF-IDF (1–2-grams) plus simple metadata flags (missing company profile or requirements, company logo, salary given, URL/email/phone present, text length).
4. Models: Logistic Regression and LinearSVC with class weighting. Both performed almost identically (PR-AUC 0.917 vs. 0.923); Logistic Regression was kept for its interpretable coefficients.
5. Chose the decision threshold on cross-validated training predictions (target: maximum recall at ≥90% precision), then evaluated once on the held-out test set.
6. Error analysis of missed scams and false alarms.

The notebook contains all charts: class balance, fraud rate by logo and company profile, precision-recall curve, confusion matrix and top features.

## How to Run
**On Kaggle:** open the notebook above, add the dataset as input, set the accelerator to *None* (no GPU needed), and click *Run All*.

**Locally:**
```bash
git clone https://github.com/Noman87370/scam-job-posting-detector.git
cd scam-job-posting-detector
pip install -r requirements.txt
# download fake_job_postings.csv from Kaggle, then open the notebook:
jupyter notebook scam_job_detector.ipynb
```

## Platform

The research above is now a running web app: an AI job search for
Germany that scores every listing for fraud risk. The model was
retrained from the notebook pipeline by `train/train_model.py` and the
retrained metrics are in `model/METRICS.md` (PR-AUC 0.914, precision
93.9%, recall 75.9% — 107 of 141 fake caught, 7 false alarms, vs. the
notebook's 0.917 / 93.1% / 76.6%). The "Gradio demo" idea from Future
Improvements is implemented as the in-app **Check a posting** tool.

**What it does**

- **Dashboard** — live job postings from the Arbeitnow API, filtered to
  Germany / remote-with-Germany, each with a fraud-probability meter,
  risk band (low/medium/high), risk explanation, and the original apply
  link. Search by title/company/location, filter by category
  (Werkstudent, Internship, Part-time, Full-time) and risk, sort by
  date or risk.
- **Check a posting** — paste any job ad and get a risk score with the
  top contributing words and rule-based indicators.
- **Ingestion** — every 30 minutes (in-process scheduler + GitHub
  Actions cron), with deduping and expiry handling. No mock or
  placeholder jobs: if nothing has been ingested yet, the dashboard
  says so honestly.
- **Predictions are risk estimates, never a verdict** — the model was
  trained on 2019-era data and scam wording changes over time.

**Run locally**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set INGEST_TOKEN
uvicorn backend.main:app --reload --port 8000
# open http://localhost:8000
```

Frontend development (optional — the backend serves the production
build from `backend/static`):

```bash
cd frontend && npm install && npm run dev
```

**API**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Status + whether the model loaded |
| GET | `/api/jobs` | List jobs (`q`, `category`, `risk_band`, `min_risk`, `max_risk`, `sort`, `page`, `per_page`) |
| GET | `/api/jobs/{id}` | One job |
| POST | `/api/predict` | Score a pasted posting (probability, risk band, top words, indicators) |
| POST | `/api/jobs/ingest` | Trigger ingestion (header `X-Ingest-Token`) |
| GET | `/api/stats` | Totals by category and risk band |

**Deploy** — see `DEPLOYMENT.md` (Render Blueprint + GitHub Actions
cron). **Architecture** — see `ARCHITECTURE.md`.

**Tests**

```bash
.venv/bin/python -m pytest tests/test_api.py tests/test_ingest.py -v
# tests/test_model.py loads the saved model artifacts; run it separately:
.venv/bin/python -m pytest tests/test_model.py -v
```

## Results
Model comparison on the test set (before threshold tuning):

| Model | PR-AUC | ROC-AUC | F1 (fake, default threshold) |
|---|---|---|---|
| Logistic Regression | 0.917 | 0.993 | 0.824 |
| LinearSVC | 0.923 | 0.993 | 0.879 |

Final model (Logistic Regression) at the tuned threshold on the test set:

| Precision | Recall | F1 | Fake caught | False alarms |
|---|---|---|---|---|
| 93.1% | 76.6% | 0.840 | 108 of 141 | 8 of 2,998 real postings |

## Key Insights
- Both linear models perform almost identically on PR-AUC, so the main gains come from handling class imbalance and choosing the decision threshold, not from the model type.
- The model flagged 116 of 3,139 test postings (3.7%); 108 of them were fake, so about 9 in 10 alerts are real scams, but about 1 in 4 scams (33 of 141) is still missed.
- Removing 2,189 duplicate or empty postings before the split prevents identical texts from appearing in both training and test data.
- Postings without a company logo or company profile are much more likely to be fake (XX% vs. XX%).
- Strongest fraud signals in the model: XX, XX, XX.
- Missed scams tend to be XX; false alarms tend to be XX.

## Limitations
- Only about 800 fake examples in total (141 in the test set), from a single dataset, so the metrics carry uncertainty; scam wording also changes over time.
- The threshold favors precision, which means roughly one in four scams is missed. A platform that prefers recall would choose a lower threshold.
- Text features alone cannot catch carefully written scams.
- Results come from one train/test split, with no external validation set.

## Future Improvements
- Sentence-embedding features (e.g. MiniLM) compared with TF-IDF.
- Gradio demo: paste a job ad, get a risk score and the words that drove it.
- Cost-based threshold (cost of a missed scam vs. cost of a false alarm).

## Repository Structure
```
├── scam-job-posting-detector.ipynb   # original research notebook
├── backend/          # FastAPI app: API, ingestion, scheduler, ML serving
├── common/           # shared text-cleaning / metadata features
├── train/            # train_model.py — reproduces the notebook pipeline
├── frontend/         # React + Vite dashboard (builds to backend/static)
├── model/            # retrained artifacts + METRICS.md
├── tests/            # pytest suite
├── .github/workflows/ingest.yml     # 30-minute ingestion cron
├── Dockerfile        # multi-stage build (Node + Python)
├── render.yaml       # Render Blueprint (web service + Postgres)
├── requirements.txt  # backend runtime dependencies
├── DEPLOYMENT.md     # exact deploy steps
├── ARCHITECTURE.md   # stack, data flow, model, API contract
└── README.md
```

## Kurzfassung (Deutsch)
Dieses Projekt erkennt betrügerische Stellenanzeigen mit TF-IDF und linearen Modellen. Da nur etwa 4,8 % der
Anzeigen gefälscht sind, wird nicht mit der Accuracy, sondern mit PR-AUC, Recall und Precision bewertet. Beim gewählten
Schwellenwert erkennt das Modell 77 % der betrügerischen Anzeigen (108 von 141) bei einer Precision von 93 %.

## Contact
**Abdullah Al Noman** · M.Sc. Medical Engineering (Medical Robotics), FAU Erlangen-Nürnberg
[GitHub](https://github.com/Noman87370)
