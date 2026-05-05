"""
Wilma — final dataset merger and train/val/test splitter.

Reads all four interim CSVs, concatenates them, runs a final
cross-dataset deduplication, and produces stratified
train (80%) / validation (10%) / test (10%) splits in data/processed/.

Run:
    python -m wilma.data.merge_datasets
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from wilma.data.schema import REQUIRED_COLUMNS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INTERIM_FILES = [
    "sms_spam.csv",
    "enron_spam.csv",
    "spamassassin.csv",
    "kaggle_fraud_email.csv",
]

VAL_SIZE = 0.10
TEST_SIZE = 0.10
RANDOM_STATE = 42


def load_interim() -> pd.DataFrame:
    frames = []
    for filename in INTERIM_FILES:
        path = INTERIM_DIR / filename
        if not path.exists():
            print(f"ERROR: missing {path}", file=sys.stderr)
            sys.exit(1)
        df = pd.read_csv(path, dtype=str)
        df["char_len"] = df["char_len"].astype(int)
        print(f"  {filename}: {len(df):>6} rows")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading interim datasets...")
    df = load_interim()
    print(f"\nTotal rows before dedup: {len(df)}")

    before = len(df)
    df = df.drop_duplicates(subset=["raw_hash"], keep="first").reset_index(drop=True)
    print(f"Dropped {before - len(df)} cross-dataset duplicates")
    print(f"Total rows after dedup:  {len(df)}")

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"ERROR: missing columns: {missing_cols}", file=sys.stderr)
        return 1
    df = df[list(REQUIRED_COLUMNS)]

    print("\nLabel distribution:")
    print(df["label"].value_counts().to_string())
    print("\nCategory distribution:")
    print(df["category"].value_counts().to_string())
    print("\nSource distribution:")
    print(df["source"].value_counts().to_string())

    print(f"\nSplitting (val={VAL_SIZE}, test={TEST_SIZE}, seed={RANDOM_STATE})...")
    train_df, temp_df = train_test_split(
        df,
        test_size=VAL_SIZE + TEST_SIZE,
        stratify=df["label"],
        random_state=RANDOM_STATE,
    )
    val_df, test_df = train_test_split(
        temp_df,
        test_size=TEST_SIZE / (VAL_SIZE + TEST_SIZE),
        stratify=temp_df["label"],
        random_state=RANDOM_STATE,
    )

    train_df = train_df.reset_index(drop=True)
    val_df = val_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    train_path = PROCESSED_DIR / "wilma_v1_train.csv"
    val_path = PROCESSED_DIR / "wilma_v1_val.csv"
    test_path = PROCESSED_DIR / "wilma_v1_test.csv"
    full_path = PROCESSED_DIR / "wilma_v1_full.csv"

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    df.to_csv(full_path, index=False)

    print(f"\n  train: {len(train_df):>6}  ->  {train_path.name}")
    print(f"  val:   {len(val_df):>6}  ->  {val_path.name}")
    print(f"  test:  {len(test_df):>6}  ->  {test_path.name}")
    print(f"  full:  {len(df):>6}  ->  {full_path.name}")

    print("\nLabel balance per split (sanity check):")
    for name, split in [("train", train_df), ("val", val_df), ("test", test_df)]:
        scam_pct = (split["label"] == "scam").mean() * 100
        print(f"  {name}: {scam_pct:5.2f}% scam")

    return 0


if __name__ == "__main__":
    sys.exit(main())
