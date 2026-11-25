"""Retrain the scam-job-posting detector, reproducing the original research
notebook (scam-job-posting-detector.ipynb) exactly as a script.

Pipeline (notebook cells 7-15, 22):
  * text = title + company_profile + description + requirements + benefits
  * clean() per common.features (lowercase, strip HTML, map Kaggle tokens,
    keep a-z only)
  * drop clean text <= 20 chars, drop duplicates on clean text
    (BEFORE splitting; 15,691 postings remain)
  * 10 metadata flags (see common.features.META_COLS)
  * split: 80/20 stratified, random_state=42 (12,552 train / 3,139 test)
  * TF-IDF 1-2 grams, min_df=3, max_df=0.9, english stop words,
    sublinear_tf, max_features=60,000
  * LogisticRegression(C=5, class_weight="balanced", max_iter=1000)
  * threshold: 5-fold CV predictions on train, max recall at precision
    >= 0.90 (else best F1); stored both as a decision-function threshold
    and as the equivalent probability threshold p = sigmoid(t), because
    for logistic regression decision_function == log-odds, so the two
    rules are mathematically identical.

Outputs (model/):
  tfidf_vectorizer.joblib, logreg_model.joblib, metadata.json, METRICS.md

Usage:  .venv/bin/python train/train_model.py
"""

import glob
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.features import META_COLS, TEXT_COLS, build_features, clean_text  # noqa: E402

SEED = 42
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "model")


def find_dataset() -> str:
    csvs = glob.glob("/kaggle/input/**/*.csv", recursive=True)
    if not csvs:
        import kagglehub

        folder = kagglehub.dataset_download(
            "shivamb/real-or-fake-fake-jobposting-prediction"
        )
        csvs = glob.glob(os.path.join(folder, "**", "*.csv"), recursive=True)
    path = next((p for p in csvs if "fake" in p.lower() or "job" in p.lower()), csvs[0])
    return path


def main() -> None:
    path = find_dataset()
    df = pd.read_csv(path)
    assert "fraudulent" in df.columns, f"Wrong file loaded ({path})."
    print(f"Loaded {path}: {df.shape}, fraud rate {df['fraudulent'].mean():.4f}")

    # Notebook cells 7-8: merge text, clean.
    df[TEXT_COLS] = df[TEXT_COLS].fillna("")
    df["text"] = df[TEXT_COLS].agg(" ".join, axis=1)
    df["clean"] = df["text"].map(clean_text)

    # Notebook cell 9: drop empties/duplicates BEFORE splitting.
    n0 = len(df)
    df = df[df["clean"].str.len() > 20].drop_duplicates(subset="clean").reset_index(drop=True)
    print(f"Removed {n0 - len(df)} duplicate/empty postings, {len(df)} left")
    print(df["fraudulent"].value_counts().to_dict())

    # Notebook cell 10: metadata flags.
    metas = [
        build_features({c: row[c] for c in TEXT_COLS + ["salary_range", "telecommuting",
                                                       "has_company_logo", "has_questions"]})[1]
        for _, row in df.iterrows()
    ]
    # build_features already merges text from the five text cols; the meta
    # flags need the raw merged text too, which build_features computes
    # internally from the same fields — consistent with the notebook.
    meta_arr = np.array(metas, dtype=float)

    # Notebook cell 11: stratified 80/20 split, seed 42.
    tr_idx, te_idx = train_test_split(
        df.index, test_size=0.2, stratify=df["fraudulent"], random_state=SEED
    )
    tr, te = df.loc[tr_idx], df.loc[te_idx]
    ytr, yte = tr["fraudulent"].values, te["fraudulent"].values
    print(f"train: {len(tr)}, test: {len(te)}")

    # Notebook cell 12: TF-IDF fitted on train only.
    vec = TfidfVectorizer(
        ngram_range=(1, 2), min_df=3, max_df=0.9, stop_words="english",
        sublinear_tf=True, max_features=60_000,
    )
    Xtr = hstack([vec.fit_transform(tr["clean"]), csr_matrix(meta_arr[tr_idx])]).tocsr()
    Xte = hstack([vec.transform(te["clean"]), csr_matrix(meta_arr[te_idx])]).tocsr()
    print(f"X train {Xtr.shape}, X test {Xte.shape}")

    # Notebook cell 14: threshold from 5-fold CV predictions on train.
    best = LogisticRegression(C=5, class_weight="balanced", max_iter=1000)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    s_cv = cross_val_predict(best, Xtr, ytr, cv=cv, method="decision_function")
    p_cv, r_cv, thr_cv = precision_recall_curve(ytr, s_cv)
    ok = np.where(p_cv[:-1] >= 0.90)[0]
    if len(ok):
        t = float(thr_cv[ok[np.argmax(r_cv[ok])]])
        rule = "max recall at precision >= 90%"
    else:
        t = float(thr_cv[np.argmax(2 * p_cv[:-1] * r_cv[:-1] / (p_cv[:-1] + r_cv[:-1] + 1e-9))])
        rule = "best F1 (no threshold reached 90% precision)"
    print(f"Threshold rule: {rule}; decision threshold = {t:.4f}")
    prob_threshold = float(1 / (1 + np.exp(-t)))
    print(f"Equivalent probability threshold = {prob_threshold:.4f}")

    # Notebook cell 15: fit on full train, predict test.
    best.fit(Xtr, ytr)
    s_te = best.decision_function(Xte)
    pred = (s_te >= t).astype(int)
    proba_te = best.predict_proba(Xte)[:, 1]
    pred_proba = (proba_te >= prob_threshold).astype(int)
    assert (pred == pred_proba).all(), "decision/probability thresholds disagree!"

    pr_auc = float(average_precision_score(yte, s_te))
    roc_auc = float(roc_auc_score(yte, s_te))
    precision = float(precision_score(yte, pred))
    recall = float(recall_score(yte, pred))
    f1 = float(f1_score(yte, pred))
    cm = confusion_matrix(yte, pred)
    tn, fp, fn, tp = (int(x) for x in cm.ravel())
    print(classification_report(yte, pred, target_names=["real", "fake"], digits=3))
    print(f"PR-AUC {pr_auc:.3f}  ROC-AUC {roc_auc:.3f}")
    print(f"Precision {precision:.3f}  Recall {recall:.3f}  F1 {f1:.3f}")
    print(f"Caught {tp} of {tp + fn} fake postings, {fp} false alarms among {fp + tn} real")

    # Top signals (notebook cell 19).
    feature_names = np.array(list(vec.get_feature_names_out()) + META_COLS)
    coef = pd.Series(best.coef_[0], index=feature_names)
    top_fraud = list(coef.nlargest(10).index)
    top_legit = list(coef.nsmallest(10).index)

    # Save artifacts.
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(vec, os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib"))
    joblib.dump(best, os.path.join(MODEL_DIR, "logreg_model.joblib"))
    metadata = {
        "dataset": "shivamb/real-or-fake-fake-jobposting-prediction (Kaggle)",
        "dataset_file": os.path.basename(path),
        "rows_raw": int(n0),
        "rows_after_cleaning": int(len(df)),
        "train_size": int(len(tr)),
        "test_size": int(len(te)),
        "fraud_rate_raw": float(df["fraudulent"].mean()),
        "seed": SEED,
        "tfidf": {
            "ngram_range": [1, 2], "min_df": 3, "max_df": 0.9,
            "stop_words": "english", "sublinear_tf": True, "max_features": 60000,
        },
        "model": "LogisticRegression(C=5, class_weight='balanced', max_iter=1000)",
        "meta_cols": META_COLS,
        "threshold_rule": rule,
        "decision_threshold": t,
        "probability_threshold": prob_threshold,
        "metrics": {
            "pr_auc": pr_auc, "roc_auc": roc_auc, "precision": precision,
            "recall": recall, "f1": f1,
            "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        },
        "top_fraud_signals": top_fraud,
        "top_legit_signals": top_legit,
    }
    with open(os.path.join(MODEL_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    metrics_md = f"""# Retrained model — measured metrics

Retrained {pd.Timestamp.now().date()} from the Kaggle dataset
`shivamb/real-or-fake-fake-jobposting-prediction` (`fake_job_postings.csv`),
reproducing the original notebook pipeline exactly
(TF-IDF 1–2 grams + 10 metadata flags, LogisticRegression C=5,
class_weight="balanced", stratified 80/20 split, seed 42, threshold = max
recall at precision >= 90% on 5-fold CV predictions).

## Dataset

| Item | Value |
|---|---|
| Rows (raw) | {n0} |
| Rows after cleaning (len > 20, deduped) | {len(df)} |
| Train / test | {len(tr)} / {len(te)} |
| Fraud rate (raw) | {df['fraudulent'].mean():.4f} |

## Test-set metrics (held-out test split, n={len(te)})

| Metric | Value |
|---|---|
| PR-AUC | {pr_auc:.3f} |
| ROC-AUC | {roc_auc:.3f} |
| Precision (at chosen threshold) | {precision:.3f} |
| Recall (at chosen threshold) | {recall:.3f} |
| F1 | {f1:.3f} |
| Decision threshold | {t:.3f} |
| Probability threshold | {prob_threshold:.3f} |

Confusion matrix (rows = actual, cols = predicted):

|  | Predicted real | Predicted fake |
|---|---|---|
| Actual real | {tn} | {fp} |
| Actual fake | {fn} | {tp} |

Caught {tp} of {tp + fn} fake postings, with {fp} false alarms among {fp + tn} real postings.

## Comparison with the README's reported numbers

README claimed: PR-AUC 0.917, precision 93.1%, recall 76.6%
(108 of 141 fake caught, 8 false alarms).

Retrained here: PR-AUC {pr_auc:.3f}, precision {precision:.1%}, recall {recall:.1%}
({tp} of {tp + fn} fake caught, {fp} false alarms).

Small differences are expected: the notebook's exact split depends on the
pandas/sklearn versions, and the Kaggle file may have been updated since the
original run. The methodology is identical.

## Top signals

Top fraud signals: {', '.join(top_fraud)}
Top legit signals: {', '.join(top_legit)}

## Note

Predictions are risk estimates, not certainty. The model estimates the
probability that a posting is fraudulent; the platform always presents it
as a risk score with an explanation, never as a definitive verdict.
"""
    with open(os.path.join(MODEL_DIR, "METRICS.md"), "w") as f:
        f.write(metrics_md)
    print("Artifacts saved to", MODEL_DIR)


if __name__ == "__main__":
    main()
