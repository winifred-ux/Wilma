"""
Wilma — SpamAssassin public corpus cleaner.

Reads data/raw/spamassassin/spam/* (RFC-822 email files, all spam) and
writes a unified-schema CSV to data/interim/spamassassin.csv.

The 2003 SpamAssassin spam corpus is mostly old commercial junk and
phishing-adjacent content. We label all of it scam / scam_other.

Run:
    python -m wilma.data.clean_spamassassin
"""

from __future__ import annotations

import csv
import hashlib
import sys
from email import message_from_binary_file
from pathlib import Path

from langdetect import DetectorFactory, detect, LangDetectException
from tqdm import tqdm

from wilma.data.cleaners import clean_text, is_valid_message
from wilma.data.email_utils import extract_subject_and_body
from wilma.data.schema import REQUIRED_COLUMNS

DetectorFactory.seed = 0

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPAM_DIR = PROJECT_ROOT / "data" / "raw" / "spamassassin" / "spam"
OUT_PATH = PROJECT_ROOT / "data" / "interim" / "spamassassin.csv"

SOURCE = "spamassassin"
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


def parse_email_file(path: Path) -> str:
    with open(path, "rb") as f:
        msg = message_from_binary_file(f)
    return extract_subject_and_body(msg)


def process() -> int:
    if not SPAM_DIR.exists():
        print(f"ERROR: spam directory not found: {SPAM_DIR}", file=sys.stderr)
        print("Run scripts/download_data.py first.", file=sys.stderr)
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in SPAM_DIR.iterdir() if p.is_file())
    print(f"Found {len(files)} email files in {SPAM_DIR}")

    seen_hashes: set[str] = set()
    kept = 0
    dropped_parse_error = 0
    dropped_too_short = 0
    dropped_duplicate = 0

    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()

        for path in tqdm(files, desc="cleaning"):
            try:
                raw_text = parse_email_file(path)
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
                "category": "scam_other",
                "source": SOURCE,
                "language": detect_language_safe(cleaned),
                "char_len": len(cleaned),
                "raw_hash": raw_hash,
            }
            writer.writerow(row)
            kept += 1

    print(f"\nProcessed: {SPAM_DIR.name}/")
    print(f"  kept:                {kept}")
    print(f"  dropped (parse err): {dropped_parse_error}")
    print(f"  dropped (too short): {dropped_too_short}")
    print(f"  dropped (duplicate): {dropped_duplicate}")
    print(f"  output:              {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(process())
