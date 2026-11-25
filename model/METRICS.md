# Retrained model — measured metrics

Retrained 2026-11-25 from the Kaggle dataset
`shivamb/real-or-fake-fake-jobposting-prediction` (`fake_job_postings.csv`),
reproducing the original notebook pipeline exactly
(TF-IDF 1–2 grams + 10 metadata flags, LogisticRegression C=5,
class_weight="balanced", stratified 80/20 split, seed 42, threshold = max
recall at precision >= 90% on 5-fold CV predictions).

## Dataset

| Item | Value |
|---|---|
| Rows (raw) | 17880 |
| Rows after cleaning (len > 20, deduped) | 15691 |
| Train / test | 12552 / 3139 |
| Fraud rate (raw) | 0.0451 |

## Test-set metrics (held-out test split, n=3139)

| Metric | Value |
|---|---|
| PR-AUC | 0.914 |
| ROC-AUC | 0.992 |
| Precision (at chosen threshold) | 0.939 |
| Recall (at chosen threshold) | 0.759 |
| F1 | 0.839 |
| Decision threshold | 1.032 |
| Probability threshold | 0.737 |

Confusion matrix (rows = actual, cols = predicted):

|  | Predicted real | Predicted fake |
|---|---|---|
| Actual real | 2991 | 7 |
| Actual fake | 34 | 107 |

Caught 107 of 141 fake postings, with 7 false alarms among 2998 real postings.

## Comparison with the README's reported numbers

README claimed: PR-AUC 0.917, precision 93.1%, recall 76.6%
(108 of 141 fake caught, 8 false alarms).

Retrained here: PR-AUC 0.914, precision 93.9%, recall 75.9%
(107 of 141 fake caught, 7 false alarms).

Small differences are expected: the notebook's exact split depends on the
pandas/sklearn versions, and the Kaggle file may have been updated since the
original run. The methodology is identical.

## Top signals

Top fraud signals: link tokurl, using link, apply using, receptionist, accion, administrative, assistant, high school, earn, line requirements
Top legit signals: text_len, english, web, client, growing, digital, new, university, experience, software

## Note

Predictions are risk estimates, not certainty. The model estimates the
probability that a posting is fraudulent; the platform always presents it
as a risk score with an explanation, never as a definitive verdict.
