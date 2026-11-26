# Model metrics

## Deployed model (notebook)

The deployed model is the logistic regression exported from the research
notebook (`model/model_artifacts.joblib`, threshold 0.949). These are the
numbers the UI reports and the only metrics that describe the deployed
model.

Test set: 3,139 postings (141 fake, 2,998 real), stratified 80/20 split,
seed 42.

| Metric | Value |
|---|---|
| PR-AUC | 0.917 |
| Precision (at threshold 0.949) | 0.931 |
| Recall (at threshold 0.949) | 0.766 |
| Decision threshold | 0.949 |

Confusion matrix (rows = actual, cols = predicted):

|  | Predicted real | Predicted fake |
|---|---|---|
| Actual real | 2990 | 8 |
| Actual fake | 33 | 108 |

Caught 108 of 141 fake postings, with 8 false alarms among 2,998 real
postings. The model flagged 116 of 3,139 test postings (3.7%).

## Separate retraining run — not deployed

Retrained 2026-11-25 from the Kaggle dataset
`shivamb/real-or-fake-fake-jobposting-prediction` (`fake_job_postings.csv`),
reproducing the original notebook pipeline exactly
(TF-IDF 1–2 grams + 10 metadata flags, LogisticRegression C=5,
class_weight="balanced", stratified 80/20 split, seed 42, threshold = max
recall at precision >= 90% on 5-fold CV predictions). This run is recorded
here only; its artifacts are not the deployed model, and the UI does not
show its numbers.

### Dataset

| Item | Value |
|---|---|
| Rows (raw) | 17880 |
| Rows after cleaning (len > 20, deduped) | 15691 |
| Train / test | 12552 / 3139 |
| Fraud rate (raw) | 0.0451 |

### Test-set metrics (held-out test split, n=3139)

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

### Comparison with the deployed (notebook) numbers

Deployed: PR-AUC 0.917, precision 93.1%, recall 76.6%
(108 of 141 fake caught, 8 false alarms).

Retrained here: PR-AUC 0.914, precision 93.9%, recall 75.9%
(107 of 141 fake caught, 7 false alarms).

Small differences are expected: the notebook's exact split depends on the
pandas/sklearn versions, and the Kaggle file may have been updated since the
original run. The methodology is identical.

### Top signals

Top fraud signals: link tokurl, using link, apply using, receptionist, accion, administrative, assistant, high school, earn, line requirements
Top legit signals: text_len, english, web, client, growing, digital, new, university, experience, software

## Note

Predictions are risk estimates, not certainty. The model estimates the
probability that a posting is fraudulent; the platform always presents it
as a risk score with an explanation, never as a definitive verdict.
