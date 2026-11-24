# Scam Job Posting Detector

[![Open in Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](YOUR_KAGGLE_NOTEBOOK_LINK)
![Python](https://img.shields.io/badge/python-3.10+-blue)
![scikit-learn](https://img.shields.io/badge/scikit--learn-ML-orange)

> Detects fraudulent job postings from text and metadata, with evaluation designed for rare-event data.
> **At the chosen threshold, the model catches XX% of fake postings at XX% precision (PR-AUC: XX).**

![Precision-recall curve](reports/figures/pr_curve.png)

## Problem Statement
Fake job ads (advance-fee scams, data harvesting) harm job seekers, and platforms need automated screening.
Only about 4.8% of postings in this dataset are fake, so accuracy is misleading: a model that always
predicts "real" already scores 95.2%. This project therefore evaluates with PR-AUC, recall and precision on
the fake class, and an explicit decision threshold.

## Dataset
[Real / Fake Job Posting Prediction (Kaggle)](https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction):
17,880 postings with 18 columns (free text plus metadata). After removing duplicate and empty texts: XX postings.
The data is not included in this repository.

## Technologies Used
Python · pandas · NumPy · SciPy · scikit-learn (TF-IDF, Logistic Regression, LinearSVC) · matplotlib · seaborn

## Approach
1. Merged title, company profile, description, requirements and benefits into one text field.
2. Cleaned the text (HTML tags, placeholder tokens for URLs, emails and phone numbers) and removed duplicates **before** splitting, to avoid train/test leakage.
3. Features: TF-IDF (1–2-grams) plus simple metadata flags (missing company profile or requirements, company logo, salary given, URL/email/phone present, text length).
4. Models: Logistic Regression and LinearSVC with class weighting.
5. Chose the decision threshold on cross-validated training predictions (maximum recall at ≥90% precision), then evaluated once on the held-out test set.
6. Error analysis of missed scams and false alarms.

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

## Results
| Model | PR-AUC | ROC-AUC | F1 (fake, default threshold) |
|---|---|---|---|
| Logistic Regression | XX | XX | XX |
| LinearSVC | XX | XX | XX |

At the chosen threshold on the test set: **XX of XX** fake postings caught, with **XX** false alarms among XX real postings
(precision XX%, recall XX%).

## Key Insights
- Postings without a company logo or company profile are much more likely to be fake (XX% vs. XX%).
- Strongest fraud signals in the model: XX, XX, XX.
- Missed scams tend to be XX (for example well-written postings with a complete company profile).
- False alarms tend to be XX.

## Visualizations
| Class balance | Fraud rate by logo / profile |
|---|---|
| ![](reports/figures/eda_class_balance.png) | ![](reports/figures/eda_fraud_rates.png) |

| Confusion matrix | Top features |
|---|---|
| ![](reports/figures/confusion_matrix.png) | ![](reports/figures/top_features.png) |

## Limitations
- Only about 800 fake examples from a single dataset; scam wording changes over time.
- Text features alone cannot catch carefully written scams.
- Results come from one train/test split, with no external validation set.

## Future Improvements
- Sentence-embedding features (e.g. MiniLM) compared with TF-IDF.
- Gradio demo: paste a job ad, get a risk score and the words that drove it.
- Cost-based threshold (cost of a missed scam vs. cost of a false alarm).

## Kurzfassung (Deutsch)
Dieses Projekt erkennt betrügerische Stellenanzeigen mit TF-IDF und logistischer Regression. Da nur etwa 4,8 % der
Anzeigen gefälscht sind, wird nicht mit der Accuracy, sondern mit PR-AUC, Recall und Precision bewertet. Beim gewählten
Schwellenwert erkennt das Modell XX % der betrügerischen Anzeigen bei einer Precision von XX %.
