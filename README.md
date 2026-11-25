# Scam Job Posting Detector (English ML model + German warning-sign checker)

Detects fraudulent job postings — English postings with an ML model trained in a Kaggle notebook, German postings with a transparent rule-based warning-sign checker — with a live job feed scored the same way.

## Live Demo

Try it at https://scam-job-detector-hob9.onrender.com. The demo runs on Render's free tier, so the first load after a pause can take up to a minute to wake up. The interface is available in German and English (toggle at the top right; German by default when the browser language is German).

**What each mode does — and does not do:**

- **English postings** are scored by the ML model (TF-IDF + logistic regression, trained on the Kaggle "Real / Fake Job Posting Prediction" dataset). Reported results on the English test set: precision 93.1%, recall 76.6% — the model misses about 1 in 4 scams and can flag real postings. Treat every result as a rough estimate, not a verdict. Never a "% chance of scam".
- **German postings** are checked against warning signs from German consumer advice centers (Verbraucherzentrale): demands for ID copies, video ident, opening a bank account, forwarding money or parcels, paying first, easy-money and task-scam wording, messenger-only contact, instant acceptance. This is a **rule-based check, not a model**: it has no ML metrics and is **not validated on labelled data**. A small synthetic sanity check (20 invented scam-like texts, 20 realistic legitimate ones) is in `tests/de_cases.csv` — it shows the rules work as intended on those examples, nothing more.
- **Other languages** are not supported. Mixed German/English text, or text the detector cannot place, asks you to choose the posting language instead of guessing.

Paste an English or German job posting (or a message you received) into the "Check a posting" form, or browse the live German listings. Text you enter is processed only to compute the result and is not stored.

## What it does

- **Check a posting** — fill in the fields of a job ad (title, company profile, description, requirements, benefits, plus four checkboxes) and get a risk level with an explanation. The posting language can be Auto (detected), Deutsch or English. Two fictional examples per language can be loaded with one click. Text you enter is processed only to compute the result and is not stored.
- **German warning-sign check** — for German postings, the rules in `backend/rules_de.py` (a plain data file) look for the warning signs listed above. Critical signs (ID/bank/forwarding/pay-first demands) mean "High risk", unless the sentence clearly describes a job duty or a right-to-work check at employment start — then the rule is downgraded to "mild" and the user sees why. The matched sentence is shown as evidence for every rule. Four optional checkboxes cover what the text alone cannot say (unsolicited offer, asked for ID/bank data, asked to open an account or pay, messenger-only contact). A "High risk" result adds an advice box: stop contact, do not send ID or bank data, keep evidence, report to the police or a consumer advice center.
- **Live job listings** — real German job postings from the Arbeitnow API, refreshed every 30 minutes. Search by title, company or location; filter by category (Werkstudent, Internship, Part-time, Full-time) and risk level; sort by date or risk. Each listing links to the original posting. English listings are scored by the ML model, German listings by the rule checker.
- **Risk levels, never a verdict** — "High risk", "Some warning signs" or "Few warning signs found". No band says "safe" or "not a scam", and no probability is shown as a "% chance of scam" (the probabilities are not calibrated). "Few warning signs found" is always followed by the line that this does not mean the offer is trustworthy.
- **UI in German and English** — all visible text lives in one translations file (`frontend/src/i18n.js`, key -> {de, en}); German uses the formal "Sie".

## How detection works

### English: ML model

TF-IDF (1–2 grams, 60k features) plus 10 metadata flags, fed into a Logistic Regression classifier (`C=5`, class-balanced). Before scoring, real URLs, email addresses and phone numbers in the input are converted to the placeholders the training data used (`#URL_x#`, `#EMAIL_x#`, `#PHONE_x#`), so the token features behave as in training.

The decision rule is the notebook's: score = `model.decision_function(X)`; "High risk" starts at a score of **0.949** (a predicted probability of about 0.72). "Some warning signs" is 0 to 0.949, "Few warning signs" below 0.

Reported results on the English test set (3,139 postings, 141 fake):

| PR-AUC | Precision | Recall | Fake caught | False alarms |
|---|---|---|---|---|
| 0.917 | 93.1% | 76.6% | 108 of 141 | 8 of 2,998 real |

The loaded model is the logistic regression from the notebook (the LinearSVC that was also compared is not used). The retrained model's own measurements (PR-AUC 0.914, precision 93.9%, recall 75.9%) are recorded in `model/METRICS.md` only — the UI shows the notebook's numbers above.

### German: rule-based warning-sign check (no ML)

The German checker (`backend/de_rules.py`, rules in `backend/rules_de.py`) has no model and no metrics. It runs case-insensitive regexes over the text — handling umlaut spellings (ä/ae, ö/oe, ü/ue, ß/ss) and variants like Video-Ident / Videoident / Video Ident — and returns the matched sentence as evidence for each rule.

- **Critical** (any one → "High risk"): asked to verify identity (Video-Ident, Identitätsprüfung, Personalausweis/Reisepass copy, Steuer-ID); asked to open or "test" a bank account (Partnerbank, Bank-Tester, Zugangsdaten, PIN, TAN); money or parcel forwarding (Finanzagent, Zahlungen weiterleiten, Provision pro Transaktion, Paketagent); must pay first (Vorkasse, Kaution, Bearbeitungsgebühr, Einzahlung, Krypto einzahlen). A critical rule is **downgraded to "mild"** when its sentence clearly describes a job duty or a legitimate right-to-work check (e.g. a bank advisor ad saying "Sie eröffnen Konten für unsere Kunden", or a work-permit check asking for a passport copy "für die Arbeitserlaubnis").
- **Strong** (weight 2): easy-money claims (ohne Erfahrung, Heimarbeit, schnelles Geld, 500 € pro Tag); task-scam wording (Produkte bewerten, Videos liken, Bestellungen optimieren, tägliche Auszahlung); WhatsApp/Telegram/Signal as the only contact channel; instant acceptance without an interview.
- **Mild** (weight 1): free-mail address as company contact; no company name, address or Impressum; three or more exclamation marks. Spelling mistakes are deliberately not used as a signal.

Banding: any critical → "High risk"; else 2 or more strong, or strong + mild totalling a weight of 3 or more → "Some warning signs"; else "Few warning signs found" (always followed by the line that this does not mean the offer is trustworthy).

**Synthetic sanity check (NOT a validation):** `tests/de_cases.csv` holds 20 fictional scam-like and 20 realistic legitimate German texts (no real company names), including tricky legitimate cases (bank advisor mentioning Konten eröffnen, a Werkstudent ad asking for a passport copy for the work permit, a small firm using a Gmail contact). `tests/test_de_rules.py` runs the checker over them and prints the shares: 19 of 20 scam-like texts flagged (high/some), 1 of 20 legitimate texts flagged (a home-office ad with no company details given). The one unflagged scam-like text has only mild signals, which deliberately do not reach "some". These numbers describe 40 invented texts, not real-world performance.

### Language routing

The "Auto" posting-language option uses langdetect (seed 0, deterministic) on text of at least 100 characters. English → ML path, German → rule path. Mixed German+English text, or text the detector cannot place, returns no risk level and asks the user to choose the posting language. Any other detected language returns "not supported". An explicit Deutsch/English choice routes directly.

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
├── backend/          # FastAPI app: API, ingestion, scheduler, ML serving,
│                     # language detection, German rule checker
├── common/           # shared text-cleaning / metadata features
├── train/            # train_model.py — reproduces the notebook pipeline
├── frontend/         # React + Vite dashboard (builds to backend/static)
│                     # src/i18n.js — all UI text, key -> {de, en}
├── model/            # model_artifacts.joblib + METRICS.md (+ legacy artifacts)
├── tests/            # pytest suite (49 tests, incl. German rule cases)
│                     # de_cases.csv — 20 fictional scam-like + 20 legit German texts
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
| POST | `/api/predict` | Check a pasted posting (100–10,000 characters total). Body: the posting fields plus `posting_language` (`auto` / `de` / `en`, default `auto`) and `context_flags` (German check only: `unsolicited`, `asked_id`, `asked_bank_or_fee`, `contact_messenger`). Returns `path` (`ml` / `de` / `needs_choice` / `unsupported`): ML result (decision score, risk band, top raising/lowering features, indicators) or German rule result (band, matched rules with evidence sentences, counts, advice flag) |
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
- English only for the ML model: it was trained on English postings. German postings use the rule-based check instead, which has no labelled validation data — its only numbers come from the 40 invented texts in the synthetic sanity check, which is not a validation.
- The Arbeitnow API does not return a company profile or requirements, so every ingested English listing is scored with those two flags set — the feed scores are thinner than a full posting check.
- Memory: the running service uses about 260 MB RSS (measured locally after several predictions), within Render's free 512 MB. The German rule checker adds no heavy dependency — langdetect was already a dependency, and no new dependency was added for this round.

## Future improvements

- **A German ML model needs labelled German data** — there is no labelled German fake-job dataset in this project, and the English model cannot be reused for German. Collecting and labelling German postings is the prerequisite.
- **Multilingual embeddings need more RAM than the free tier offers** — sentence embeddings (e.g. MiniLM) would exceed Render's free 512 MB alongside the current stack, so they are not an option on this hosting plan.
- Sentence-embedding features (e.g. MiniLM) compared with TF-IDF, on a paid tier.
- Cost-based threshold (cost of a missed scam vs. cost of a false alarm).
- More job sources beyond Arbeitnow.

## Kurzfassung (Deutsch)

Dieses Projekt erkennt betrügerische Stellenanzeigen auf zwei Wegen. **Englische Anzeigen** werden von einem ML-Modell (TF-IDF + logistische Regression) bewertet, trainiert auf dem Kaggle-Datensatz „Real / Fake Job Posting Prediction". Gemessene Ergebnisse auf den englischen Testdaten: Präzision 93,1 %, Recall 76,6 % — das Modell übersieht etwa jede vierte betrügerische Anzeige. **Deutsche Anzeigen** werden mit einer regelbasierten Prüfung gegen Warnsignale deutscher Verbraucherzentralen geprüft (Ausweiskopie, Video-Ident, Kontoeröffnung, Geld oder Pakete weiterleiten, Vorkasse, schnelles Geld, WhatsApp als einziger Kontakt). Diese Prüfung ist kein Modell und hat keine validierten Kennzahlen — sie wurde nur an 40 erfundenen Beispieltexten getestet. Die Live-Plattform zeigt echte deutsche Stellenanzeigen und ein Formular, in das man eine englische oder deutsche Stellenanzeige einfügen und prüfen kann: https://scam-job-detector-hob9.onrender.com

## Contact

**Abdullah Al Noman** · M.Sc. Medical Engineering (Medical Robotics), FAU Erlangen-Nürnberg
[GitHub](https://github.com/Noman87370)
