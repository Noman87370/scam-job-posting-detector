# Scam Job Posting Detector

Detects fraudulent job postings. English postings are scored by an ML model (TF-IDF + logistic regression, trained on a Kaggle dataset). German postings are checked against warning signs from German consumer advice centres, using a rule-based checker. A live feed of German job listings is scored the same way.

Live demo: https://scam-job-detector-hob9.onrender.com

The demo runs on Render's free tier, so the first load after a pause can take about a minute to wake up. The interface is in German and English (toggle at the top right; German by default when the browser language is German).

## 1. What the project does

- **Check a posting.** Paste an English or German job posting (or a message you received) into the "Check a posting" form and get a risk level with an explanation. The posting language can be Auto (detected), Deutsch or English. Two fictional examples per language can be loaded with one click. Text you enter is processed only to compute the result and is not stored.
- **Live job listings.** Real German job postings from the Arbeitnow API, refreshed every 30 minutes. Search by title, company or location; filter by category (Werkstudent, Internship, Part-time, Full-time, Other) and risk level; sort by date or risk. Each listing links to the original posting.
- **Risk levels, not verdicts.** Results are "High risk", "Some warning signs" or "Few warning signs found". No band says "safe" or "not a scam", and no probability is shown as a "% chance of scam" (the model probabilities are not calibrated). "Few warning signs found" is always followed by the line that this does not mean the offer is trustworthy.

## 2. Why two detection approaches

The ML model was trained on English postings only, so it cannot judge German text. German postings are therefore checked with a rule-based checker built from warning signs published by German consumer advice centres (Verbraucherzentrale). The two paths share the same three risk bands and the same result format, so the feed and the form behave the same way for both languages. Postings in other languages are not supported; mixed German/English text, or text the detector cannot place, asks the user to choose the posting language instead of guessing.

## 3. Dataset and preprocessing

Source: [Real / Fake Job Posting Prediction (Kaggle)](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction) (`shivamb/real-or-fake-fake-jobposting-prediction`, file `fake_job_postings.csv`). 17,880 postings, 15,691 after removing duplicates and empty texts (clean text longer than 20 characters, deduplicated on the cleaned text, before splitting). 707 of the 15,691 are fake (806 fake in the raw data). Stratified 80/20 split, seed 42: 12,552 train / 3,139 test. The data is not included in this repository.

Preprocessing (notebook cells 7–10, shared with the app via `common/features.py`):

- Text is title + company profile + description + requirements + benefits, joined with spaces.
- Cleaning: lowercase, strip HTML, replace real URLs, email addresses and phone numbers with the placeholders the training data used (`#URL_x#`, `#EMAIL_x#`, `#PHONE_x#`), then keep a–z only. Before scoring, live input goes through the same placeholder step, so the token features behave as in training.
- 10 metadata flags: telecommuting, has_company_logo, has_questions, has_url_token, has_email_token, has_phone_token, no_profile, no_requirements, has_salary, text_len (log length of the cleaned text, scaled by 1/10).

## 4. ML architecture

TF-IDF (1–2 grams, min_df=3, max_df=0.9, English stop words, sublinear TF, max 60,000 features) plus the 10 metadata flags (60,010 features total), fed into `LogisticRegression(C=5, class_weight="balanced", max_iter=1000)`. The notebook also compared a LinearSVC (C=0.5, class-balanced); it scored slightly higher on PR-AUC (0.923 vs 0.917) but is not used — the deployed model is the logistic regression.

Decision rule: score = `model.decision_function(X)`; "High risk" starts at a score of **0.949** (a predicted probability of about 0.72). Bands: high ≥ 0.949, some 0 to 0.949, few below 0. The threshold was chosen on 5-fold cross-validation predictions on the training set as the threshold with maximum recall at precision ≥ 90%.

The app loads the committed artifact `model/model_artifacts.joblib` (a dict with `vec`, `model`, `meta_cols`, `threshold`, `feature_names`, exported from the notebook — see "Export the model" below). The artifact carries threshold 0.949, which is the threshold the app uses. The legacy pair `model/logreg_model.joblib` + `model/tfidf_vectorizer.joblib` is kept as a fallback if the bundle is absent. Deploys do not retrain. `requirements.txt` pins scikit-learn 1.9.1, the version the artifacts were trained with.

The checker also returns 9 rule-based indicators (upfront fee, wire transfer, urgency language, no company profile, no requirements, no logo, phone/email/URL tokens in text, very short posting) and the top 5 features raising and top 3 lowering the score, with per-feature contributions (x_i · coef_i).

## 5. Evaluation results

Notebook results (test set, 3,139 postings, 141 fake) — these are the numbers the UI reports:

| PR-AUC | Precision | Recall | Fake caught | False alarms |
|---|---|---|---|---|
| 0.917 | 93.1% | 76.6% | 108 of 141 | 8 of 2,998 real |

The model flagged 116 of 3,139 test postings (3.7%); 108 of them were fake. About 1 in 4 scams is still missed.

Retrained results (`train/train_model.py`, same pipeline, recorded in `model/METRICS.md` and `model/metadata.json` only — the UI does not show them): PR-AUC 0.914, precision 93.9%, recall 75.9%, 107 of 141 fake caught, 7 false alarms, with its own threshold 1.0322. The small differences come from the split depending on library versions and the Kaggle file possibly having changed since the original run. The app does not use the retrained threshold: it uses the threshold stored in `model_artifacts.joblib` (0.949). Note that retraining writes a new `model_artifacts.joblib` carrying the retrained threshold, so check the threshold before deploying a retrained model (see `DEPLOYMENT.md`).

## 6. German warning-sign detection

Rule-based, not ML. Rules live in `backend/rules_de.py` (a plain data file); the checker is `backend/de_rules.py`. It runs case-insensitive regexes over the text, handling umlaut spellings (ä/ae, ö/oe, ü/ue, ß/ss) and variants such as Video-Ident / Videoident / Video Ident, and returns the matched sentence as evidence for each rule.

- **Critical** (any one → "High risk"): asked to verify identity (Video-Ident, Identitätsprüfung, Personalausweis/Reisepass copy, Steuer-ID); asked to open or "test" a bank account (Partnerbank, Bank-Tester, Zugangsdaten, PIN, TAN); money or parcel forwarding (Finanzagent, Zahlungen weiterleiten, Provision pro Transaktion, Paketagent); must pay first (Vorkasse, Kaution, Bearbeitungsgebühr, Einzahlung, Krypto einzahlen). A critical rule is **downgraded to "mild"** when its sentence clearly describes a job duty or a legitimate right-to-work check at employment start (e.g. a bank advisor ad saying "Sie eröffnen Konten für unsere Kunden", or a work-permit check asking for a passport copy "für die Arbeitserlaubnis").
- **Strong** (weight 2): easy-money claims (ohne Erfahrung, Heimarbeit, schnelles Geld, 500 € pro Tag); task-scam wording (Produkte bewerten, Videos liken, Bestellungen optimieren, tägliche Auszahlung); WhatsApp/Telegram/Signal as the only contact channel; instant acceptance without an interview.
- **Mild** (weight 1): free-mail address as company contact; no company name, address or Impressum; three or more exclamation marks. Spelling mistakes are deliberately not used as a signal.

Banding: any critical → "High risk"; else 2 or more strong, or 1 strong with total weight ≥ 3 → "Some warning signs"; else "Few warning signs found".

Four optional checkboxes cover what the text alone cannot say: unsolicited offer (strong), asked for ID/bank data (critical), asked to open an account or pay (critical), messenger-only contact (strong). A "High risk" result adds an advice box (stop contact, do not send ID or bank data, keep evidence, report to the police or a consumer advice centre) with a link to the Verbraucherzentrale advice page: https://www.verbraucherzentrale.de/wissen/digitale-welt/datenschutz/gefaelschte-stellenanzeigen-was-ist-jobscamming-28475

**No validation metrics.** The German checker has no ML metrics and is not validated on labelled data. The only numbers come from a small synthetic sanity check: `tests/de_cases.csv` holds 20 fictional scam-like and 20 realistic legitimate German texts (no real company names). The checker flags 19 of the 20 scam-like texts (high/some) and 1 of the 20 legitimate texts (a home-office ad with no company details given); the one missed scam-like text has only mild signals, which deliberately do not reach "some". These numbers describe 40 invented texts, not real-world performance.

**Rule fix, 2026-11-26.** The identity-check rule (`de_id_check`) used to match the bare verb stem "identifizier*" / "identifik*", which flagged ordinary duty wording ("Du identifizierst Wachstumspotenziale", "Identifikation von Engpässen") — all 58 High-risk feed rows carried that one rule. It now matches only the noun "Identitätsprüfung". Real scam wording is still covered by the Video-Ident and ID-copy rules. The three wrongly flagged sentences are regression tests in `tests/test_de_rules.py`. The rule set has a version (`RULES_VERSION` in `backend/rules_de.py`, currently `2026-11-26-v2`), stored with every German feed row; when a rule changes, the next ingest re-scores stored German rows whose stored version differs, so a fix heals the feed instead of leaving old rows wrong.

**Language routing.** The "Auto" posting-language option uses langdetect (seed 0, deterministic) on text of at least 100 characters. English → ML path, German → rule path. Mixed German+English text (second language probability ≥ 0.20), or text the detector cannot place (top probability < 0.5), returns no risk level and asks the user to choose the posting language. Any other detected language returns "not supported". An explicit Deutsch/English choice routes directly.

## 7. Application features

- **Check a posting** (`POST /api/predict`): structured form (title, company, description, requirements, benefits, company profile, location, salary range, checkboxes for telecommuting, company logo, screening questions, salary stated), posting-language selector (Auto/Deutsch/English), four German context checkboxes, two fictional examples per language. ML results show decision score, risk band, top raising/lowering features and indicators. German results show band, matched rules with evidence sentences, counts, advice flag and link.
- **Job feed** (`GET /api/jobs`): listings from Arbeitnow, scored at ingest by language (English by ML, German by rules; other languages get an ML score but no band is shown). 20 jobs per page.
- **Ingestion**: Arbeitnow API, up to 10 pages × 300 jobs per run, Germany filter (location in Germany or a German city, or remote with no location stated), dedupe on (source, external_id) and on normalised (title, company, location), expiry (posted_at older than 60 days, or not seen in the latest full ingest and older than 7 days — marked expired, never deleted). The Arbeitnow API returns no company profile or requirements, so every ingested English listing is scored with those two flags set — feed scores are thinner than a full posting check.
- **UI in German and English**: all visible text lives in one translations file (`frontend/src/i18n.js`, key → {de, en}); German uses the formal "Sie".

## 8. Tech stack

- **Backend:** FastAPI, SQLAlchemy (SQLite locally, PostgreSQL in production), APScheduler
- **Frontend:** React 19 + Vite (build output served by the backend from `backend/static`)
- **ML:** scikit-learn, TF-IDF + Logistic Regression, joblib artifacts, langdetect
- **Ingestion:** Arbeitnow API, GitHub Actions cron (every 30 min)
- **Hosting:** Render (free tier) + free PostgreSQL
- **Tests:** pytest + FastAPI TestClient (53 tests)

## 9. Project structure

```
├── scam-job-posting-detector.ipynb   # original research notebook (Kaggle)
├── backend/          # FastAPI app: API, ingestion, scheduler, ML serving,
│                     # language detection, German rule checker
├── common/           # shared text-cleaning / metadata features
├── train/            # train_model.py — reproduces the notebook pipeline
├── frontend/         # React + Vite dashboard (builds to backend/static)
│                     # src/i18n.js — all UI text, key -> {de, en}
├── model/            # model_artifacts.joblib + metadata.json + METRICS.md
│                     # (+ legacy logreg_model.joblib / tfidf_vectorizer.joblib)
├── tests/            # pytest suite, incl. German rule cases (de_cases.csv:
│                     # 20 fictional scam-like + 20 legit German texts)
├── .github/workflows/ingest.yml     # 30-minute ingestion cron
├── Dockerfile        # two-stage build (Node + Python)
├── render.yaml       # Render Blueprint (web service + Postgres)
├── requirements.txt  # backend runtime dependencies
├── DEPLOYMENT.md     # deploy steps
└── ARCHITECTURE.md   # stack, data flow, model, API contract
```

## 10. Installation

```bash
git clone https://github.com/Noman87370/scam-job-posting-detector.git
cd scam-job-posting-detector
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set INGEST_TOKEN
uvicorn backend.main:app --reload --port 8000
# open http://localhost:8000
```

On Windows use `.venv\Scripts\activate` instead of `source .venv/bin/activate`, and `copy .env.example .env` instead of `cp`.

Frontend development (optional — the backend serves the production build from `backend/static`):

```bash
cd frontend && npm install && npm run dev
```

**Research notebook** (written for Kaggle; it reads the dataset from `/kaggle/input`):

```bash
pip install -r train/requirements.txt
pip install jupyter
# download fake_job_postings.csv from Kaggle, then:
jupyter notebook scam-job-posting-detector.ipynb
```

**Retrain the model** (fetches the dataset via kagglehub if it is not under `/kaggle/input`):

```bash
pip install -r train/requirements.txt
python train/train_model.py   # writes artifacts to model/, incl. model_artifacts.joblib
```

**Tests:**

```bash
.venv/bin/python -m pytest tests/ -v
```

### Export the model from the notebook

After training in the notebook, export the artifacts the app loads, and print the scikit-learn version (the `requirements.txt` pin must match it — a mismatch breaks loading the pickled model):

```python
joblib.dump({"vec": vec, "model": best, "meta_cols": meta_cols, "threshold": float(t),
             "feature_names": feature_names}, "model_artifacts.joblib")
print("scikit-learn version:", sklearn.__version__)
```

Here `t` is the tuned decision threshold (0.949 in the notebook), `vec` the fitted `TfidfVectorizer`, `best` the fitted logistic regression, `meta_cols` the 10 metadata column names in order, and `feature_names = list(vec.get_feature_names_out()) + meta_cols`. Copy the resulting `model_artifacts.joblib` to `model/` and commit it — the app loads it directly, and deploys do not retrain.

## 11. API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Status + whether the model loaded |
| GET | `/api/jobs` | List jobs (`q`, `category`, `risk_band`, `min_risk`, `max_risk`, `sort`, `include_expired`, `page`, `per_page` — default 20, max 100) |
| GET | `/api/jobs/{id}` | One job (404 if missing) |
| POST | `/api/predict` | Check a pasted posting (100–10,000 characters total). Body: `title`, `company`, `description`, `requirements`, `benefits`, `company_profile`, `location`, `salary_range`, `telecommuting`, `has_company_logo`, `has_questions`, `has_salary`, plus `posting_language` (`auto` / `de` / `en`, default `auto`) and `context_flags` (German check only: `unsolicited`, `asked_id`, `asked_bank_or_fee`, `contact_messenger`). Returns `path` (`ml` / `de` / `needs_choice` / `unsupported`): ML result (decision score, risk band, top raising/lowering features, indicators) or German rule result (band, matched rules with evidence sentences, counts, advice flag). 400 when the total input is under 100 or over 10,000 characters, or `posting_language` is invalid; 503 if the model is unavailable |
| POST | `/api/jobs/ingest` | Trigger ingestion (header `X-Ingest-Token`). 401 without the token; 503 if no token is configured. Returns `source`, `fetched`, `kept`, `inserted`, `updated`, `duplicates`, `expired_marked`, `error` |
| GET | `/api/stats` | Totals by category and risk band, last ingest, model info |

Example:

```bash
curl -X POST https://scam-job-detector-hob9.onrender.com/api/predict \
  -H "Content-Type: application/json" \
  -d '{"title": "Work from home, earn $5000/week", "description": "Urgent hiring, no experience needed, pay a small registration fee to start immediately and earn money fast from home."}'
```

## 12. Deployment

See `DEPLOYMENT.md` for the exact steps. In short: Render Blueprint (`render.yaml`) creates the web service + PostgreSQL, and the GitHub Actions workflow (`.github/workflows/ingest.yml`) triggers ingestion every 30 minutes. The workflow needs two repository secrets (Settings → Secrets and variables → Actions):

- `APP_URL` — the live service URL, e.g. `https://scam-job-detector-hob9.onrender.com` (no trailing slash)
- `INGEST_TOKEN` — must match the `INGEST_TOKEN` env var of the Render web service

The free Render service sleeps after 15 minutes idle (cold start ~60 s), so the in-app scheduler alone cannot keep the feed fresh — the GitHub Actions cron is what keeps it updated, and it also wakes the service. The free Postgres database expires after 90 days.

## 13. Limitations and future improvements

Limitations:

- Only 707 fake examples after cleaning (141 in the test set), from a single dataset, so the metrics carry uncertainty; scam wording also changes over time.
- The threshold favours precision, which means roughly one in four scams is missed. A platform that prefers recall would choose a lower threshold.
- Text features alone cannot catch carefully written scams.
- Results come from one train/test split, with no external validation set.
- English only for the ML model: it was trained on English postings. German postings use the rule-based check instead, which has no labelled validation data — its only numbers come from the 40 invented texts in the synthetic sanity check, which is not a validation.
- The Arbeitnow API does not return a company profile or requirements, so every ingested English listing is scored with those two flags set — the feed scores are thinner than a full posting check.
- The model was trained on 2019-era English Kaggle data; the German checker has no labelled validation data.

Listings source: listings come from the [Arbeitnow](https://www.arbeitnow.com) free public job-board API (`https://www.arbeitnow.com/api/job-board-api`, no key required, updated hourly). Its terms ask for a link back to Arbeitnow.com (present in the footer) and for no abuse; the site's terms of service also say API permission can be revoked at any time, and the use licence (personal, non-commercial) is not explicit about whether it covers API data — so this feed is a non-commercial demo, and the feed should be removed if Arbeitnow objects. Ingestion fetches up to 10 pages per run (300 jobs per page) every 30 minutes rather than re-reading the feed per visitor.

Future improvements:

- A German ML model needs labelled German data — there is no labelled German fake-job dataset in this project, and the English model cannot be reused for German. Collecting and labelling German postings is the prerequisite.
- Sentence-embedding features (e.g. MiniLM) compared with TF-IDF, on a paid tier — embeddings would exceed Render's free 512 MB alongside the current stack, so they are not an option on this hosting plan.
- Cost-based threshold (cost of a missed scam vs. cost of a false alarm).
- More job sources beyond Arbeitnow.

## Contact

**Abdullah Al Noman** · M.Sc. Medical Engineering (Medical Robotics), FAU Erlangen-Nürnberg
[GitHub](https://github.com/Noman87370)
