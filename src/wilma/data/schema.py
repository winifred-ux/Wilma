"""
Wilma — unified dataset schema.

Every cleaned dataset (SMS Spam, Enron, SpamAssassin, Kaggle Fraud, and
future Nigerian SMS) is normalized into rows matching the schema below.
This means downstream training code never has to know which dataset a
row came from — it just sees uniform columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

# ---------------------------------------------------------------------------
# Label vocabulary
# ---------------------------------------------------------------------------

# Binary label (used for V1 launch)
BinaryLabel = Literal["legitimate", "scam"]

# Multi-class category (used for V1.5 / V2 expansion).
# Every row gets a category. Legitimate messages get "legitimate".
# When we don't yet know the specific scam type, we use "scam_other".
Category = Literal[
    "legitimate",
    "phishing",
    "advance_fee_419",
    "fake_otp",
    "impersonation",
    "romance",
    "fake_loan",
    "crypto_scam",
    "scam_other",
]

ALL_CATEGORIES: Final[tuple[Category, ...]] = (
    "legitimate",
    "phishing",
    "advance_fee_419",
    "fake_otp",
    "impersonation",
    "romance",
    "fake_loan",
    "crypto_scam",
    "scam_other",
)

SCAM_CATEGORIES: Final[frozenset[Category]] = frozenset(
    c for c in ALL_CATEGORIES if c != "legitimate"
)

# Source identifiers — each dataset gets a stable string we can group by.
DataSource = Literal[
    "uci_sms_spam",
    "enron_spam",
    "spamassassin",
    "kaggle_fraud_email",
    "local_nigerian_sms",
]

# ---------------------------------------------------------------------------
# Row schema
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "id",          # unique row id, stable across reruns
    "text",        # the cleaned, anonymized message text
    "label",       # binary: "legitimate" or "scam"
    "category",    # multi-class category
    "source",      # which dataset this came from
    "language",    # ISO 639-1 code, or "und" for undetermined
    "char_len",    # character length of cleaned text (for filtering)
    "raw_hash",    # sha1 of the original raw text (for dedup + provenance)
)


@dataclass(frozen=True, slots=True)
class WilmaRow:
    """In-memory representation of a single training row."""

    id: str
    text: str
    label: BinaryLabel
    category: Category
    source: DataSource
    language: str
    char_len: int
    raw_hash: str

    def to_dict(self) -> dict[str, object]:
        return {col: getattr(self, col) for col in REQUIRED_COLUMNS}