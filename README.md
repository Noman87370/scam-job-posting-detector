# 🛡️ Scam Job Posting Detector
### English ML Model + German Warning-Sign Detection

An AI-powered job fraud detection platform that identifies potentially fraudulent job postings using two approaches: **Machine Learning for English postings** and **rule-based warning-sign detection for German postings**. Includes a live job search platform for Germany with automated risk assessment.

<p align="center">
  <a href="https://scam-job-detector-hob9.onrender.com">
    <img src="https://img.shields.io/badge/🚀_Live_Demo-Try_Now-2ea44f?style=for-the-badge" alt="Live Demo">
  </a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-Machine_Learning-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react" alt="React">
  <img src="https://img.shields.io/badge/scikit--learn-ML-orange?logo=scikitlearn" alt="Scikit-learn">
  <img src="https://img.shields.io/badge/Tests-49_Passing-brightgreen?logo=pytest" alt="Tests">
  <img src="https://img.shields.io/badge/Deployment-Render-purple?logo=render" alt="Render">
</p>

---

## 🚀 Live Demo

**Application:** https://scam-job-detector-hob9.onrender.com

The application is available in both English and German. German is selected by default when the browser language is German.

**Note:** The application runs on Render's free tier. After inactivity, the first load may take approximately 60 seconds while the service wakes up.

## 📌 Project Overview

Online job scams are becoming increasingly sophisticated, making it difficult for job seekers to distinguish legitimate opportunities from fraudulent advertisements.

This project addresses the problem through two separate detection approaches:

| Detection System | Approach | Language |
|---|---|---|
| Machine Learning Detector | TF-IDF + Logistic Regression | English |
| Warning-Sign Detector | Rule-based analysis using regex | German |

Rather than applying an English-trained model to German advertisements, the platform uses a separate German warning-sign checker based on common fraud patterns identified by German consumer advice centers (Verbraucherzentrale).

### Key Features

- **AI-Powered Fraud Detection:** Uses TF-IDF and Logistic Regression to identify potentially fraudulent English job postings.
- **German Scam Detection:** Identifies suspicious German job advertisements using transparent rule-based warning signs.
- **Live Job Search:** Retrieves real job listings from Germany through the Arbeitnow API.
- **Automated Risk Assessment:** Evaluates live job listings using the appropriate detection system.
- **Explainable Results:** Shows contributing words, matched warning signs, and evidence sentences.
- **Custom Job Analysis:** Paste a job advertisement or suspicious recruitment message for analysis.
- **Smart Filtering:** Search by job title, company, and location; filter by employment category and risk level.
- **Bilingual Interface:** Supports German and English.
- **Privacy-Conscious Processing:** Text entered into the checking form is processed to calculate the result and is not stored.

## 🧠 How Detection Works

The application uses different detection pipelines depending on the language of the job advertisement.

### 1. English Job Postings – Machine Learning

<badge color="success">Machine Learning</badge>

The English detection system uses a Logistic Regression classifier trained on the Kaggle Real / Fake Job Posting Prediction dataset.

**Model Architecture:**

- TF-IDF Vectorization (unigrams and bigrams)
- 60,000 text features
- 10 additional metadata flags
- Class-balanced Logistic Regression (`C=5`)
- Optimized decision threshold

Before prediction, real URLs, email addresses, and phone numbers are converted into placeholders matching the training data format.

**Decision Threshold:**

The application uses the original notebook's decision function:

- High risk: Score ≥ 0.949
- Some warning signs: Score between 0 and 0.949
- Few warning signs: Score below 0

These are risk categories, not calibrated probabilities or definitive scam judgments.

### English Model Performance

Evaluation on the English test dataset:

| Metric | Result |
|---|---:|
| PR-AUC | 0.917 |
| Precision | 93.1% |
| Recall | 76.6% |
| Fake postings detected | 108 / 141 |
| False alarms | 8 / 2,998 |

The model detects approximately 77% of fraudulent postings while maintaining 93.1% precision.

**Important:** Approximately one in four fraudulent postings is still missed. A low-risk result does not guarantee that a job advertisement is legitimate.

The application loads the Logistic Regression model trained in the original notebook. The separately retrained model has its own metrics documented in `model/METRICS.md`.

### 2. German Job Postings – Rule-Based Detection

<badge color="info">Rule-Based Detection · No ML</badge>

German job advertisements are evaluated using transparent rules based on common fraud patterns and warning signs highlighted by German consumer advice centers.

The checker uses case-insensitive regular expressions and handles common German spelling variations, including:

- ä / ae
- ö / oe
- ü / ue
- ß / ss

It also recognizes different spellings of terms such as Video-Ident, Videoident, and Video Ident.

**Detection Categories:**

| Category | Examples | Weight |
|---|---|---:|
| Critical | ID verification demands, suspicious bank-account opening, money or parcel forwarding, advance payments | High risk |
| Strong | Easy-money promises, task scams, messenger-only contact, instant acceptance without interviews | 2 |
| Mild | Free email addresses, missing company information, excessive exclamation marks | 1 |

**Critical warning signs include:**

- Requests for passport or identity card copies for suspicious verification.
- Video-Ident or identity verification demands.
- Requests to open or test bank accounts.
- Requests for PIN, TAN, or online banking credentials.
- Money or parcel forwarding.
- Advance payments, registration fees, or cryptocurrency deposits.

**Important Context Handling**

The checker considers the context of a suspicious phrase.

For example, a legitimate bank-advisor advertisement mentioning that employees open accounts for customers should not automatically be treated as fraudulent.

Similarly, a legitimate employer requesting a passport copy for a right-to-work check at the appropriate stage of employment should not automatically trigger the highest risk classification.

The matched sentence is displayed as evidence for each detected rule.

**Risk Classification:**

- Any critical warning sign → High risk.
- Two or more strong warning signs → Some warning signs.
- Strong and mild signals with a combined weight of at least 3 → Some warning signs.
- Otherwise → Few warning signs found.

The system also includes four optional context checkboxes covering unsolicited offers, requests for identity or bank information, payment or account-opening requests, and messenger-only contact.

A high-risk result provides practical safety advice: stop contact, do not share identity or banking information, preserve evidence, and report suspicious activity to the police or a consumer advice center.

**Validation Disclaimer:** The German checker is rule-based, not a machine learning model. It has no labelled real-world validation dataset or validated performance metrics.

### German Synthetic Sanity Check

A small test dataset is included in `tests/de_cases.csv`:

| Test Category | Examples | Flagged |
|---|---:|---:|
| Fictional scam-like texts | 20 | 19 |
| Fictional legitimate texts | 20 | 1 |

These results come from 40 invented examples, not real-world validation. They demonstrate that the rules behave as intended on selected examples, not that the system achieves a particular real-world accuracy.

### 3. Language Detection and Routing

The application automatically determines which detection pipeline to use.

```text
             Job Advertisement
                     |
                     ▼
              Language Detection
                     |
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       English     German     Other
          |          |          |
          ▼          ▼          ▼
       TF-IDF     Rule-Based   Unsupported
          |       Detection    Language
          ▼          |
     Logistic        ▼
     Regression   Warning Signs
          |          |
          └────┬─────┘
               ▼
         Risk Assessment
               |
               ▼
       Explainable Results
```

The automatic language detector uses `langdetect` with a fixed seed for deterministic results.

- English → Machine Learning pipeline.
- German → Rule-based detection.
- Mixed German and English → User is asked to select the language.
- Other languages → Not supported.

The automatic detector requires at least 100 characters of text.

## 📊 Live Job Search Platform

The application also includes a live job search system for Germany.

Job advertisements are retrieved from the [Arbeitnow API](https://www.arbeitnow.com).

**Features:**

- Search by job title, company, or location.
- Filter by Werkstudent, Internship, Part-time, and Full-time.
- Filter by risk category.
- Sort listings by publication date or risk.
- View individual job advertisements.
- Access the original application links.

Each listing is assessed using the appropriate detection method:

- English listings → Machine Learning model.
- German listings → Rule-based warning-sign checker.

The job feed is refreshed every 30 minutes using automated ingestion.

**Important:** The Arbeitnow API does not provide a company profile or job requirements for every listing. Therefore, some metadata features are unavailable when scoring live English listings.

## 📁 Dataset

**Source:** [Real / Fake Job Posting Prediction – Kaggle](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction)

| Dataset Information | Value |
|---|---:|
| Original job postings | 17,880 |
| After cleaning | 15,691 |
| Training samples | 12,552 |
| Testing samples | 3,139 |
| Fake postings in test set | 141 |
| Fake posting proportion | Approximately 4.8% |

The dataset contains real and fraudulent English job advertisements.

Duplicates and empty postings were removed before the stratified train/test split.

The dataset is not included in this repository.

**Research Notebook:** `scam-job-posting-detector.ipynb`

**Note:** The English dataset is not used to train the German rule-based checker.

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React 19, Vite |
| Machine Learning | Scikit-learn, TF-IDF, Logistic Regression |
| NLP | Text preprocessing, Langdetect |
| Rule-Based Detection | Python, Regular Expressions |
| Data Processing | Pandas, NumPy |
| Database | SQLite, PostgreSQL |
| ORM | SQLAlchemy |
| Model Storage | Joblib |
| Scheduling | APScheduler |
| Job Data Source | Arbeitnow API |
| Testing | Pytest |
| Deployment | Render |
| Automation | GitHub Actions |
| Containerization | Docker |

## 🏗️ Project Structure

```text
Scam-Job-Posting-Detector/
│
├── scam-job-posting-detector.ipynb
│
├── backend/
│   ├── main.py
│   ├── de_rules.py
│   └── rules_de.py
│
├── common/
│   └── Shared text-cleaning and metadata features
│
├── train/
│   └── train_model.py
│
├── frontend/
│   ├── src/
│   │   └── i18n.js
│   └── React + Vite application
│
├── model/
│   ├── model_artifacts.joblib
│   └── METRICS.md
│
├── tests/
│   ├── de_cases.csv
│   └── pytest test suite
│
├── .github/
│   └── workflows/
│       └── ingest.yml
│
├── Dockerfile
├── render.yaml
├── requirements.txt
├── DEPLOYMENT.md
├── ARCHITECTURE.md
└── README.md
```

## ⚙️ Installation & Local Setup

### Prerequisites

- Python
- Node.js and npm (optional for frontend development)
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/Noman87370/Scam-Job-Posting-Detector.git

cd Scam-Job-Posting-Detector
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate the environment:

**Windows:**

```bash
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Configure `INGEST_TOKEN` inside your `.env` file.

### 5. Start the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

Open the application:

http://localhost:8000

### 6. Run the Frontend (Optional)

The backend serves the production frontend build from `backend/static`.

For frontend development:

```bash
cd frontend

npm install

npm run dev
```

### 7. Open the Research Notebook

Install the research dependencies:

```bash
pip install pandas matplotlib seaborn jupyter
```

Download `fake_job_postings.csv` from Kaggle and run:

```bash
jupyter notebook scam-job-posting-detector.ipynb
```

### 8. Retrain the ML Model

```bash
pip install -r train/requirements.txt

python train/train_model.py
```

The training script writes the model artifacts to the `model/` directory.

### 9. Run Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

The test suite covers the application and German warning-sign detection rules.

## 🔌 API Documentation

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application status and model availability |
| GET | `/api/jobs` | Retrieve and filter job listings |
| GET | `/api/jobs/{id}` | Retrieve an individual job |
| POST | `/api/predict` | Analyze a job advertisement |
| POST | `/api/jobs/ingest` | Trigger job ingestion |
| GET | `/api/stats` | Statistics by category and risk level |

### Job Prediction API

`POST /api/predict`

Accepts a job advertisement with a total text length of 100–10,000 characters.

Supported fields include:

- `posting_language`: `auto`, `de`, or `en`.
- `context_flags`: Optional context information for German detection.

German context flags:

- `unsolicited`
- `asked_id`
- `asked_bank_or_fee`
- `contact_messenger`

The response includes the detection path:

- `ml`
- `de`
- `needs_choice`
- `unsupported`

Depending on the detection path, the API returns the ML decision score and contributing features or German warning signs, evidence sentences, risk classification, and advice indicators.

### Example API Request

```bash
curl -X POST https://scam-job-detector-hob9.onrender.com/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Work from home, earn $5000/week",
    "description": "Urgent hiring, no experience needed, pay a small registration fee to start immediately and earn money fast from home."
  }'
```

## ☁️ Deployment

The application is deployed on Render.

**Deployment Architecture:**

- Render Web Service for the FastAPI backend.
- PostgreSQL for persistent job data.
- Docker multi-stage build for frontend and backend.
- GitHub Actions for automated job ingestion.
- Arbeitnow API for live German job listings.

### GitHub Actions Configuration

The ingestion workflow runs every 30 minutes.

Configure the following repository secrets:

| Secret | Description |
|---|---|
| `APP_URL` | Live Render application URL |
| `INGEST_TOKEN` | Must match the Render service environment variable |

Example:

```text
APP_URL=https://scam-job-detector-hob9.onrender.com
```

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for detailed deployment instructions.

**Render Free Tier:** The service sleeps after 15 minutes of inactivity. A cold start can take approximately 60 seconds. GitHub Actions helps maintain the ingestion schedule and wake the service.

## 🔍 Job Listings Data Source

Live job advertisements are retrieved from the [Arbeitnow Job Board API](https://www.arbeitnow.com/api/job-board-api).

- Free public API.
- No API key required.
- Job ingestion approximately every 30 minutes.
- Cached ingestion rather than fetching the entire feed for every visitor.

The feed is intended as a non-commercial demonstration. Arbeitnow's API terms and permission conditions apply, and the feed should be removed if permission is withdrawn or the service objects to its use.

## 🔬 Key Research Insights

- Both linear models perform almost identically on PR-AUC, suggesting that class imbalance handling and decision-threshold optimization are important factors.
- The English model flagged 116 of 3,139 test postings (3.7%); 108 were fraudulent.
- Approximately 9 out of 10 flagged postings were fraudulent in the original test results.
- Removing duplicate and empty postings before splitting helps prevent data leakage.
- German rule-based detection provides interpretable warning signs without pretending that an English-trained model understands German advertisements.
- Context-aware rules help distinguish suspicious identity and banking requests from legitimate employment procedures.

## ⚠️ Limitations

- The English ML model was trained on a single Kaggle dataset with approximately 800 fraudulent examples.
- Only 141 fraudulent postings were included in the test set.
- The English model misses approximately one in four fraudulent postings at the selected threshold.
- The results come from one train/test split, without an external validation dataset.
- German detection is rule-based and has no labelled real-world validation data.
- The German checker was tested using only 40 fictional examples. These are not real-world performance metrics.
- Other languages are currently unsupported.
- Carefully written fraudulent advertisements may avoid the existing text-based warning signs.
- Live listings may have incomplete metadata, limiting the English model's available features.
- Fraud patterns change over time, requiring regular review and improvements.

## 🔮 Future Improvements

- **German ML Model:** Collect and label real German job advertisements to develop and validate a dedicated German fraud detection model.
- **Multilingual Detection:** Extend language support beyond English and German.
- **Sentence Embeddings:** Compare TF-IDF with models such as MiniLM on hosting with sufficient memory.
- **Threshold Optimization:** Introduce cost-sensitive threshold selection based on the consequences of missed scams and false alarms.
- **Additional Job Sources:** Integrate more job APIs beyond Arbeitnow.
- **Company Verification:** Add company reputation and verification signals.
- **Model Evaluation:** Introduce external validation datasets and more comprehensive testing.

## 🇩🇪 Kurzfassung (Deutsch)

Dieses Projekt erkennt betrügerische Stellenanzeigen mit zwei unterschiedlichen Methoden.

**Englische Stellenanzeigen:** Ein Machine-Learning-Modell mit TF-IDF und logistischer Regression analysiert englische Anzeigen. Auf dem englischen Testdatensatz erreicht das Modell eine Precision von 93,1 % und einen Recall von 76,6 %.

**Deutsche Stellenanzeigen:** Ein regelbasiertes System erkennt typische Warnsignale, beispielsweise Ausweiskopien, Video-Ident, verdächtige Kontoeröffnungen, Geldweiterleitungen, Vorauszahlungen und unseriöse Messenger-Kommunikation.

Die deutsche Prüfung ist kein Machine-Learning-Modell und besitzt keine validierten Kennzahlen. Sie wurde lediglich mit 40 fiktiven Beispieltexten getestet.

Die Live-Plattform durchsucht echte Stellenanzeigen in Deutschland und bewertet diese mit dem jeweils passenden Erkennungssystem.

**Live-Demo:** https://scam-job-detector-hob9.onrender.com

## 👨‍💻 Author

**Abdullah Al Noman**

M.Sc. Medical Engineering – Medical Robotics  
Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)

**Research Interests:** Machine Learning, Artificial Intelligence, Computer Vision, Medical Imaging, and Data Analysis.

[![GitHub](https://img.shields.io/badge/GitHub-Noman87370-181717?style=for-the-badge&logo=github)](https://github.com/Noman87370)

---

<p align="center">
  <b>Building safer job-search experiences through Machine Learning and explainable fraud detection.</b>
</p>
