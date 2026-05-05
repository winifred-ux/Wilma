"""
Wilma — Enron-Spam dataset cleaner.

Reads data/raw/enron_spam/enron_spam_data.csv and writes a
unified-schema CSV to data/interim/enron_spam.csv.

The 'Subject' and 'Message' columns are concatenated (with a blank
line between) to form the text field. ~33,000 rows total; expect
processing to take 1-3 minutes due to language detection.

Run:
    python -m wilma.data.clean_enron_spam
"""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import pandas as pd
from langdetect import DetectorFactory, detect, LangDetectException
from tqdm import tqdm

from wilma.data.cleaners import clean_text, is_valid_message
from wilma.data.schema import REQUIRED_COLUMNS

DetectorFactory.seed = 0

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "enron_spam" / "enron_spam_data.csv"
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "enron_spam.csv"

SOURCE = "enron_spam"
# Language detection on huge emails is slow and barely more accurate
# than a 500-char sample. Truncate aggressively for this purpose only.
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


def map_label(raw_label: str) -> tuple[str, str] | None:
    raw_label = str(raw_label).strip().lower()
    if raw_label == "ham":
        return ("legitimate", "legitimate")
    if raw_label == "spam":
        return ("scam", "scam_other")
    return None


def combine_subject_message(subject: object, message: object) -> str:
    """Combine Subject and Message into one text field, NaN-safe."""
    parts = []
    if isinstance(subject, str) and subject.strip():
        parts.append(subject.strip())
    if isinstance(message, str) and message.strip():
        parts.append(message.strip())
    return "\n\n".join(parts)


def process() -> int:
    if not RAW_PATH.exists():
        print(f"ERROR: raw file not found: {RAW_PATH}", file=sys.stderr)
        print("Run scripts/download_data.py first.", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading {RAW_PATH.name} ...")
    df = pd.read_csv(RAW_PATH, dtype=str, encoding="utf-8")
    print(f"  {len(df)} rows loaded")

    seen_hashes: set[str] = set()
    kept = 0
    dropped_invalid_label = 0
    dropped_duplicate = 0
    dropped_too_short = 0
    label_counts: dict[str, int] = {}

    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()

        for _, row in tqdm(df.iterrows(), total=len(df), desc="cleaning"):
            mapped = map_label(row.get("Spam/Ham", ""))
            if mapped is None:
                dropped_invalid_label += 1
                continue
            binary_label, category = mapped

            raw_text = combine_subject_message(row.get("Subject"), row.get("Message"))
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

            out_row = {
                "id": stable_id(SOURCE, raw_hash),
                "text": cleaned,
                "label": binary_label,
                "category": category,
                "source": SOURCE,
                "language": detect_language_safe(cleaned),
                "char_len": len(cleaned),
                "raw_hash": raw_hash,
            }
            writer.writerow(out_row)

            kept += 1
            label_counts[binary_label] = label_counts.get(binary_label, 0) + 1

    print(f"\nProcessed: {RAW_PATH.name}")
    print(f"  kept:               {kept}")
    print(f"  dropped (label):    {dropped_invalid_label}")
    print(f"  dropped (too short):{dropped_too_short}")
    print(f"  dropped (duplicate):{dropped_duplicate}")
    print(f"  label counts:       {label_counts}")
    print(f"  output:             {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(process())