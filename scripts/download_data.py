"""
Wilma — Day 2 dataset downloader.

Downloads the four foundational public scam/spam datasets used for
Wilma V1 training:

    1. UCI SMS Spam Collection
    2. Enron-Spam (preprocessed CSV mirror)
    3. SpamAssassin spam corpus (phishing-adjacent samples)
    4. Kaggle Fraudulent Email Corpus (Nigerian 419 emails)

All datasets are saved under data/raw/<dataset_name>/ and never modified
in place. Subsequent cleaning steps work from copies in data/interim/.

Usage:
    python scripts/download_data.py
    python scripts/download_data.py --only sms_spam
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

DATASETS: dict[str, dict] = {
    "sms_spam": {
        "description": "UCI SMS Spam Collection (5,574 SMS messages, EN)",
        "url": "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
        "kind": "zip",
    },
    "enron_spam": {
        "description": "Enron-Spam preprocessed (MWiechmann mirror)",
        "url": "https://github.com/MWiechmann/enron_spam_data/raw/master/enron_spam_data.zip",
        "kind": "zip",
    },
    "spamassassin": {
        "description": "SpamAssassin public spam corpus sample",
        "url": "https://spamassassin.apache.org/old/publiccorpus/20030228_spam.tar.bz2",
        "kind": "tarball",
    },
    "kaggle_fraud_email": {
        "description": "Kaggle Fraudulent Email Corpus (Nigerian 419 emails)",
        "kaggle_ref": "rtatman/fraudulent-email-corpus",
        "kind": "kaggle",
    },
}


def ensure_raw_dir() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path) -> None:
    """Stream-download a file with a progress bar."""
    print(f"  → downloading {url}")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(
            total=total, unit="B", unit_scale=True, desc=dest.name, leave=False
        ) as bar:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))


def fetch_zip(name: str, url: str) -> None:
    target_dir = RAW_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)
    archive = target_dir / "download.zip"
    download_file(url, archive)
    print(f"  → extracting into {target_dir}")
    with zipfile.ZipFile(archive) as z:
        z.extractall(target_dir)
    archive.unlink()


def fetch_tarball(name: str, url: str) -> None:
    target_dir = RAW_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)
    archive = target_dir / Path(url).name
    download_file(url, archive)
    print(f"  → extracting into {target_dir}")
    subprocess.run(
        ["tar", "-xjf", str(archive), "-C", str(target_dir)], check=True
    )
    archive.unlink()


def fetch_kaggle(name: str, ref: str) -> None:
    target_dir = RAW_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"  → downloading Kaggle dataset: {ref}")
    subprocess.run(
        [
            "kaggle",
            "datasets",
            "download",
            "-d",
            ref,
            "-p",
            str(target_dir),
            "--unzip",
        ],
        check=True,
    )


def fetch(name: str) -> None:
    info = DATASETS[name]
    print(f"\n[{name}] {info['description']}")

    target_dir = RAW_DIR / name
    if target_dir.exists() and any(
        f for f in target_dir.iterdir() if f.name != "README.md"
    ):
        print(f"  ✓ already present at {target_dir} — skipping")
        return

    try:
        if info["kind"] == "zip":
            fetch_zip(name, info["url"])
        elif info["kind"] == "tarball":
            fetch_tarball(name, info["url"])
        elif info["kind"] == "kaggle":
            fetch_kaggle(name, info["kaggle_ref"])
        else:
            raise ValueError(f"unknown kind: {info['kind']}")
        print(f"  ✓ saved to {target_dir}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ FAILED: {exc}", file=sys.stderr)
        if target_dir.exists():
            # Preserve the README we created earlier
            for item in target_dir.iterdir():
                if item.name != "README.md":
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Wilma raw datasets")
    parser.add_argument(
        "--only",
        choices=list(DATASETS),
        help="Download a single dataset by name",
    )
    args = parser.parse_args()

    ensure_raw_dir()

    names = [args.only] if args.only else list(DATASETS)
    for name in names:
        try:
            fetch(name)
        except Exception:  # noqa: BLE001
            print(f"\nAborted after failure on '{name}'.", file=sys.stderr)
            return 1

    print("\nAll requested datasets downloaded.")
    print(f"Raw data lives in: {RAW_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())