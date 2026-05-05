"""
Wilma — apply the rule-based categorizer to processed datasets.

Reads data/processed/wilma_v1_*.csv, applies categorize_message() to
recategorize \'scam_other\' rows where possible, and overwrites the
files in place.

Run:
    python -m wilma.data.recategorize
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from wilma.data.categorize import categorize_message

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SPLITS = ["train", "val", "test", "full"]


def recategorize_split(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"wilma_v1_{name}.csv"
    print(f"\n[{name}] reading {path.name}...")
    df = pd.read_csv(path)
    n = len(df)

    before = df["category"].value_counts().to_dict()

    new_categories = []
    for _, row in tqdm(df.iterrows(), total=n, desc=f"  {name}"):
        new_categories.append(
            categorize_message(row["text"], row["category"])
        )
    df["category"] = new_categories

    after = df["category"].value_counts().to_dict()

    print(f"  Before: {before}")
    print(f"  After:  {after}")

    df.to_csv(path, index=False)
    print(f"  Wrote {path.name} ({n} rows)")
    return df


def main() -> int:
    if not PROCESSED_DIR.exists():
        print("ERROR: data/processed/ does not exist", file=sys.stderr)
        return 1

    for name in SPLITS:
        recategorize_split(name)

    print("\n" + "=" * 60)
    print("Recategorization complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
