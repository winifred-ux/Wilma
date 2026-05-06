"""
Wilma -- DistilBERT fine-tuning for 4-class scam categorization.

Trains on the 4 categories with sufficient data:
    legitimate, scam_other, advance_fee_419, commercial_spam.

The 6 rare categories (phishing, fake_otp, fake_loan, crypto_scam,
romance, impersonation) are filtered out of training but preserved
in the dataset for future evaluation.

Run:
    python -m wilma.models.train_distilbert_multiclass
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
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_DIR = PROJECT_ROOT / "models" / "distilbert_v1_multiclass"
RESULTS_DIR = PROJECT_ROOT / "results"

MODEL_NAME = "distilbert-base-multilingual-cased"
MAX_LENGTH = 256
BATCH_SIZE = 16
NUM_EPOCHS = 3
LEARNING_RATE = 2e-5
WEIGHT_DECAY = 0.01
WARMUP_STEPS = 200
SEED = 42

TRAIN_CATEGORIES = ["legitimate", "scam_other", "advance_fee_419", "commercial_spam"]
LABEL2ID = {cat: i for i, cat in enumerate(TRAIN_CATEGORIES)}
ID2LABEL = {i: cat for cat, i in LABEL2ID.items()}


def load_split(name):
    df = pd.read_csv(DATA_DIR / f"wilma_v1_{name}.csv")
    df = df[df["category"].isin(TRAIN_CATEGORIES)].copy()
    df["text"] = df["text"].astype(str)
    df["label_id"] = df["category"].map(LABEL2ID)
    return Dataset.from_pandas(
        df[["text", "label_id"]].rename(columns={"label_id": "labels"}),
        preserve_index=False,
    )


def tokenize(examples, tokenizer):
    return tokenizer(
        examples["text"],
        truncation=True,
        max_length=MAX_LENGTH,
        padding=False,
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {
        "accuracy": float((preds == labels).mean()),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "f1_weighted": f1_score(labels, preds, average="weighted"),
        "precision_macro": precision_score(
            labels, preds, average="macro", zero_division=0
        ),
        "recall_macro": recall_score(
            labels, preds, average="macro", zero_division=0
        ),
    }


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(SEED)
    np.random.seed(SEED)

    if torch.backends.mps.is_available():
        device_label = "mps (Apple Silicon GPU)"
    elif torch.cuda.is_available():
        device_label = f"cuda ({torch.cuda.get_device_name(0)})"
    else:
        device_label = "cpu (will be very slow)"
    print(f"Device: {device_label}")
    print(f"Categories: {TRAIN_CATEGORIES}")

    print(f"\nLoading tokenizer: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    print("Loading data splits (filtering to trainable categories)...")
    train_ds = load_split("train")
    val_ds = load_split("val")
    print(f"  train: {len(train_ds)} rows")
    print(f"  val:   {len(val_ds)} rows")

    print("\nTokenizing...")
    train_ds = train_ds.map(
        lambda x: tokenize(x, tokenizer), batched=True, remove_columns=["text"]
    )
    val_ds = val_ds.map(
        lambda x: tokenize(x, tokenizer), batched=True, remove_columns=["text"]
    )

    print(f"\nLoading model: {MODEL_NAME} (4-class head)")
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(TRAIN_CATEGORIES),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

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
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        save_total_limit=2,
        seed=SEED,
        report_to="none",
        dataloader_num_workers=2,
        fp16=False,
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
    print("Starting multi-class training...")
    print("=" * 60)
    trainer.train()

    print("\n" + "=" * 60)
    print("Final validation evaluation")
    print("=" * 60)
    final_metrics = trainer.evaluate()
    for k, v in final_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")

    print("\nDetailed per-class report (validation set):")
    preds_output = trainer.predict(val_ds)
    y_pred = np.argmax(preds_output.predictions, axis=-1)
    y_true = preds_output.label_ids
    label_names = [ID2LABEL[i] for i in range(len(TRAIN_CATEGORIES))]
    print(f"\nCategories order: {label_names}")
    print("\nConfusion matrix (rows=actual, cols=predicted):")
    print(confusion_matrix(y_true, y_pred))
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, target_names=label_names, digits=4))

    print(f"\nSaving model to {MODEL_DIR}")
    trainer.save_model(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    metrics_path = RESULTS_DIR / "distilbert_multiclass_val.json"
    metrics_path.write_text(json.dumps({
        k: float(v) if isinstance(v, (int, float, np.floating)) else str(v)
        for k, v in final_metrics.items()
    }, indent=2))
    print(f"Metrics saved: {metrics_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
