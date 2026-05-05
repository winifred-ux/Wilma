"""
Wilma — Kaggle Fraudulent Email Corpus cleaner.

Reads data/raw/kaggle_fraud_email/fradulent_emails.txt (mbox format,
~3,900 concatenated Nigerian 419 / advance-fee-fraud emails) and writes
a unified-schema CSV to data/interim/kaggle_fraud_email.csv.

This is the Nigeria-specific 419 corpus — Wilma's cultural and
linguistic moat. We label everything here as scam / advance_fee_419.

Run:
    python -m wilma.data.clean_kaggle_fraud
"""

from __future__ import annotations

import csv
import hashlib
import sys
from email import message_from_string
from pathlib import Path
from typing import Iterator

from langdetect import DetectorFactory, detect, LangDetectException
from tqdm import tqdm

from wilma.data.cleaners import clean_text, is_valid_message
from wilma.data.email_utils import extract_subject_and_body
from wilma.data.schema import REQUIRED_COLUMNS

DetectorFactory.seed = 0

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = (
    PROJECT_ROOT / "data" / "raw" / "kaggle_fraud_email" / "fradulent_emails.txt"
)
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "kaggle_fraud_email.csv"

SOURCE = "kaggle_fraud_email"
LANG_DETECT_TRUNCATE = 500


def detect_language_safe(text: str) -> str:
    if len(text) < 10:
        return "und"
    try:
        return detect(text[:LANG_DETECT_TRUNCATE])
    except LangDetectException:
        return "und"


def hash_raw(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def stable_id(source: str, raw_hash: str) -> str:
    return f"{source}_{raw_hash[:16]}"


def count_messages(path: Path) -> int:
    """Quickly count messages by counting 'From ' separator lines."""
    count = 0
    with open(path, "rb") as f:
        for line in f:
            if line.startswith(b"From "):
                count += 1
    return count


def iter_mbox_messages(path: Path) -> Iterator[str]:
    """Yield raw email text blobs from an mbox file.

    Splits on lines starting with 'From ' (the mbox separator).
    Uses latin-1 encoding to read bytes verbatim; ftfy fixes any
    encoding issues during the clean_text stage.
    """
    current: list[str] = []
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        for line in f:
            if line.startswith("From ") and current:
                yield "".join(current)
                current = []
            current.append(line)
        if current:
            yield "".join(current)


def process() -> int:
    if not RAW_PATH.exists():
        print(f"ERROR: raw file not found: {RAW_PATH}", file=sys.stderr)
        print("Run scripts/download_data.py first.", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Counting messages in {RAW_PATH.name}...")
    total = count_messages(RAW_PATH)
    print(f"  {total} messages found")

    seen_hashes: set[str] = set()
    kept = 0
    dropped_parse_error = 0
    dropped_too_short = 0
    dropped_duplicate = 0

    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()

        for raw_email in tqdm(
            iter_mbox_messages(RAW_PATH), total=total, desc="cleaning"
        ):
            try:
                msg = message_from_string(raw_email)
                raw_text = extract_subject_and_body(msg)
            except Exception:
                dropped_parse_error += 1
                continue

            if not raw_text:
                dropped_too_short += 1
                continue

            cleaned = clean_text(raw_text)
            if not is_valid_message(cleaned):
                dropped_too_short += 1
                continue

            raw_hash = hash_raw(raw_text)
            if raw_hash in seen_hashes:
                dropped_duplicate += 1
                continue
            seen_hashes.add(raw_hash)

            row = {
                "id": stable_id(SOURCE, raw_hash),
                "text": cleaned,
                "label": "scam",
                "category": "advance_fee_419",
                "source": SOURCE,
                "language": detect_language_safe(cleaned),
                "char_len": len(cleaned),
                "raw_hash": raw_hash,
            }
            writer.writerow(row)
            kept += 1

    print(f"\nProcessed: {RAW_PATH.name}")
    print(f"  kept:                {kept}")
    print(f"  dropped (parse err): {dropped_parse_error}")
    print(f"  dropped (too short): {dropped_too_short}")
    print(f"  dropped (duplicate): {dropped_duplicate}")
    print(f"  output:              {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(process())
