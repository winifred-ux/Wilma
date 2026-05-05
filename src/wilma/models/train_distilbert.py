"""
Wilma — DistilBERT fine-tuning for binary scam classification.

Fine-tunes distilbert-base-multilingual-cased on the processed training
set, evaluates on the validation set, and saves the best checkpoint.

Run:
    python -m wilma.models.train_distilbert
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from datasets import Dataset
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models" / "distilbert_v1"
RESULTS_DIR = PROJECT_ROOT / "results"

MODEL_NAME = "distilbert-base-multilingual-cased"
MAX_LENGTH = 256          # tokens; messages truncated past this
BATCH_SIZE = 16           # safe for M4 Max with 256-token sequences
NUM_EPOCHS = 3
LEARNING_RATE = 2e-5      # standard for transformer fine-tuning
WEIGHT_DECAY = 0.01
WARMUP_STEPS = 200
SEED = 42

LABEL2ID = {"legitimate": 0, "scam": 1}
ID2LABEL = {0: "legitimate", 1: "scam"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_split(name: str) -> Dataset:
    df = pd.read_csv(DATA_DIR / f"wilma_v1_{name}.csv")
    df = df[["text", "label"]].dropna()
    df["text"] = df["text"].astype(str)
    df["label_id"] = df["label"].map(LABEL2ID)
    if df["label_id"].isna().any():
        bad = df[df["label_id"].isna()]["label"].unique()
        raise ValueError(f"Unknown labels in {name}: {bad}")
    return Dataset.from_pandas(df[["text", "label_id"]].rename(columns={"label_id": "labels"}), preserve_index=False)


def tokenize(examples, tokenizer):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=MAX_LENGTH,
        padding=False,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    probs = torch.softmax(torch.from_numpy(logits), dim=-1).numpy()[:, 1]
    return {
        "accuracy": (preds == labels).mean(),
        "f1_scam": f1_score(labels, preds, pos_label=1),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "precision_scam": precision_score(labels, preds, pos_label=1),
        "recall_scam": recall_score(labels, preds, pos_label=1),
        "roc_auc": roc_auc_score(labels, probs),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    # Device check
    if torch.backends.mps.is_available():
        device_label = "mps (Apple Silicon GPU)"
    elif torch.cuda.is_available():
        device_label = f"cuda ({torch.cuda.get_device_name(0)})"
    else:
        device_label = "cpu (will be very slow)"
    print(f"Device: {device_label}")

    print(f"\nLoading tokenizer: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    print("Loading data splits...")
    train_ds = load_split("train")
    val_ds = load_split("val")
    print(f"  train: {len(train_ds)} rows | val: {len(val_ds)} rows")

    print("\nTokenizing (this takes ~30s for 31k rows)...")
    train_ds = train_ds.map(lambda x: tokenize(x, tokenizer), batched=True, remove_columns=["text"])
    val_ds = val_ds.map(lambda x: tokenize(x, tokenizer), batched=True, remove_columns=["text"])

    print(f"\nLoading model: {MODEL_NAME} (binary classification head)")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=2,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    print("\nConfiguring training...")
    args = TrainingArguments(
        output_dir=str(MODEL_DIR / "checkpoints"),
        overwrite_output_dir=True,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        warmup_steps=WARMUP_STEPS,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="steps",
        logging_steps=100,
        load_best_model_at_end=True,
        metric_for_best_model="f1_scam",
        greater_is_better=True,
        save_total_limit=2,
        seed=SEED,
        report_to="none",     # disable W&B / TensorBoard for now
        dataloader_num_workers=2,
        fp16=False,           # MPS doesn't support fp16; bf16 supported on newer torch
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    print("\n" + "=" * 60)
    print("Starting training...")
    print("=" * 60)
    trainer.train()

    print("\n" + "=" * 60)
    print("Final evaluation on validation set")
    print("=" * 60)
    final_metrics = trainer.evaluate()
    for k, v in final_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")

    # Detailed validation report
    print("\nGenerating detailed classification report...")
    preds_output = trainer.predict(val_ds)
    y_pred = np.argmax(preds_output.predictions, axis=-1)
    y_true = preds_output.label_ids
    label_names = [ID2LABEL[i] for i in sorted(ID2LABEL)]
    print("\nConfusion matrix [legit, scam] x [legit, scam]:")
    print(confusion_matrix(y_true, y_pred))
    print("\nFull classification report:")
    print(classification_report(y_true, y_pred, target_names=label_names, digits=4))

    print(f"\nSaving final model to {MODEL_DIR}")
    trainer.save_model(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    metrics_path = RESULTS_DIR / "distilbert_v1_val.json"
    metrics_path.write_text(json.dumps({k: float(v) if isinstance(v, (int, float, np.floating)) else str(v)
                                        for k, v in final_metrics.items()}, indent=2))
    print(f"Metrics saved: {metrics_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
