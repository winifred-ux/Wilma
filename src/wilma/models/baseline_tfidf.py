"""
Wilma — TF-IDF + Logistic Regression baseline.

Trains a classical text classifier on the processed training set and
evaluates on the validation set. This is the bar that DistilBERT must
beat to justify its complexity.

Run:
    python -m wilma.models.baseline_tfidf
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    train = pd.read_csv(DATA_DIR / "wilma_v1_train.csv")
    val = pd.read_csv(DATA_DIR / "wilma_v1_val.csv")
    return train, val


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),       # unigrams + bigrams
                    min_df=2,                 # ignore words seen <2 times
                    max_df=0.95,              # ignore words in >95% of docs
                    max_features=50_000,
                    sublinear_tf=True,        # log scaling helps long docs
                    token_pattern=r"[a-zA-Z<>]+",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    C=4.0,
                    class_weight=None,        # data is balanced enough
                    n_jobs=-1,
                ),
            ),
        ]
    )


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> dict:
    """Compute headline metrics + classification report."""
    return {
        "precision_scam": precision_score(y_true, y_pred, pos_label="scam"),
        "recall_scam": recall_score(y_true, y_pred, pos_label="scam"),
        "f1_scam": f1_score(y_true, y_pred, pos_label="scam"),
        "f1_macro": f1_score(y_true, y_pred, average="macro"),
        "roc_auc": roc_auc_score(
            (y_true == "scam").astype(int),
            y_proba[:, list(np.unique(y_true)).index("scam")],
        ),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classification_report": classification_report(y_true, y_pred, digits=4),
    }


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    train, val = load_data()
    print(f"  train: {len(train)} rows | val: {len(val)} rows")

    print("\nBuilding pipeline (TF-IDF + LogisticRegression)...")
    pipe = build_pipeline()

    print("Training...")
    pipe.fit(train["text"].astype(str), train["label"])

    print("Evaluating on validation set...")
    y_true = val["label"].to_numpy()
    y_pred = pipe.predict(val["text"].astype(str))
    y_proba = pipe.predict_proba(val["text"].astype(str))

    metrics = evaluate(y_true, y_pred, y_proba)

    print("\n" + "=" * 60)
    print("Baseline: TF-IDF + Logistic Regression — VALIDATION RESULTS")
    print("=" * 60)
    print(f"  Precision (scam): {metrics['precision_scam']:.4f}")
    print(f"  Recall    (scam): {metrics['recall_scam']:.4f}")
    print(f"  F1        (scam): {metrics['f1_scam']:.4f}")
    print(f"  F1        (macro): {metrics['f1_macro']:.4f}")
    print(f"  ROC AUC:           {metrics['roc_auc']:.4f}")
    print("\nConfusion matrix [legit, scam] x [legit, scam]:")
    print(np.array(metrics["confusion_matrix"]))
    print("\nFull classification report:")
    print(metrics["classification_report"])

    model_path = MODEL_DIR / "baseline_tfidf.joblib"
    joblib.dump(pipe, model_path)
    print(f"\nModel saved: {model_path}")

    metrics_path = RESULTS_DIR / "baseline_tfidf_val.json"
    metrics_to_save = {k: v for k, v in metrics.items() if k != "classification_report"}
    metrics_to_save["classification_report"] = metrics["classification_report"]
    metrics_path.write_text(json.dumps(metrics_to_save, indent=2))
    print(f"Metrics saved: {metrics_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
