"""
Wilma — fastText baseline.

Trains a fastText supervised classifier on the processed training set
and evaluates on the validation set. fastText uses character n-grams,
which makes it more robust than bag-of-words to typos — common in
scam messages.

Run:
    python -m wilma.models.baseline_fasttext
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import fasttext
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"


def normalize_for_fasttext(text: str) -> str:
    """fastText input must be a single line — strip newlines and excess whitespace."""
    return " ".join(str(text).split())


def write_fasttext_file(df: pd.DataFrame, path: Path) -> None:
    """Write df to fastText's expected format: __label__<label> <text> per line."""
    with open(path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            text = normalize_for_fasttext(row["text"])
            label = row["label"]
            f.write(f"__label__{label} {text}\n")


def evaluate(model, val_df: pd.DataFrame) -> dict:
    """Predict on val and compute headline metrics."""
    texts = [normalize_for_fasttext(t) for t in val_df["text"].astype(str)]
    y_true = val_df["label"].to_numpy()

    # Predict top label only, then derive scam probability robustly.
    labels, probs = model.predict(texts, k=1)

    y_pred = []
    scam_proba = []
    for label_pair, prob_pair in zip(labels, probs):
        top_label = label_pair[0].replace("__label__", "")
        top_prob = float(prob_pair[0])
        y_pred.append(top_label)
        # Probability of scam is top_prob if scam is predicted, else 1 - top_prob
        scam_p = top_prob if top_label == "scam" else 1.0 - top_prob
        scam_proba.append(scam_p)

    y_pred = np.array(y_pred)
    scam_proba = np.array(scam_proba)

    return {
        "precision_scam": precision_score(y_true, y_pred, pos_label="scam"),
        "recall_scam": recall_score(y_true, y_pred, pos_label="scam"),
        "f1_scam": f1_score(y_true, y_pred, pos_label="scam"),
        "f1_macro": f1_score(y_true, y_pred, average="macro"),
        "roc_auc": roc_auc_score((y_true == "scam").astype(int), scam_proba),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classification_report": classification_report(y_true, y_pred, digits=4),
    }


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    train = pd.read_csv(DATA_DIR / "wilma_v1_train.csv")
    val = pd.read_csv(DATA_DIR / "wilma_v1_val.csv")
    print(f"  train: {len(train)} rows | val: {len(val)} rows")

    with tempfile.TemporaryDirectory() as tmp:
        train_path = Path(tmp) / "train.txt"
        print(f"\nWriting training file in fastText format...")
        write_fasttext_file(train, train_path)

        print("Training fastText...")
        model = fasttext.train_supervised(
            input=str(train_path),
            epoch=25,
            lr=0.5,
            wordNgrams=2,
            minCount=2,
            dim=100,
            loss="softmax",
            verbose=2,
            thread=4,
        )

    print("\nEvaluating on validation set...")
    metrics = evaluate(model, val)

    print("\n" + "=" * 60)
    print("Baseline: fastText — VALIDATION RESULTS")
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

    model_path = MODEL_DIR / "baseline_fasttext.bin"
    model.save_model(str(model_path))
    print(f"\nModel saved: {model_path}")

    metrics_path = RESULTS_DIR / "baseline_fasttext_val.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"Metrics saved: {metrics_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
