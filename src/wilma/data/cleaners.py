"""
Wilma — text cleaning utilities.

Centralized text normalization functions used by every dataset cleaner.
Pipeline order: fix_encoding → normalize_whitespace → anonymize_pii.

Anonymization replaces PII (phones, emails, URLs, money amounts) with
placeholder tokens. This protects privacy AND improves model quality
by forcing the model to learn linguistic patterns instead of memorizing
specific phone numbers or URLs.
"""

from __future__ import annotations

import re
import html as _html
from typing import Final

import ftfy

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_PHONE_PATTERNS: Final = [
    re.compile(r"\+\d{1,3}[\s\-.]?\(?\d{1,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"),
    re.compile(r"\b0[789][01]\d[\s\-.]?\d{3}[\s\-.]?\d{4}\b"),
    re.compile(r"\b\d{10,15}\b"),
]

_URL_PATTERNS: Final = [
    re.compile(r"https?://\S+", re.IGNORECASE),
    re.compile(r"\bwww\.\S+", re.IGNORECASE),
    re.compile(
        r"\b[a-z0-9][a-z0-9\-]*\.(?:com|net|org|info|biz|ng|co|io|me|tv|xyz|link)\b\S*",
        re.IGNORECASE,
    ),
]

_EMAIL_PATTERN: Final = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
)

_MONEY_PATTERN: Final = re.compile(
    r"(?:\u20a6|NGN|N|\$|USD|\u00a3|GBP|\u20ac|EUR)\s?\d{1,3}(?:[,]\d{3})*(?:\.\d{1,2})?",
    re.IGNORECASE,
)

_MULTI_WS: Final = re.compile(r"\s+")
_HTML_TAG_PATTERN: Final = re.compile(r"<[^>]+>")

# ---------------------------------------------------------------------------
# Cleaning functions
# ---------------------------------------------------------------------------


def strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities (&amp;, &nbsp;, etc.).

    Crude — uses regex rather than a real HTML parser. Sufficient for
    scam-email cleaning where we just need to extract readable text;
    not appropriate for security-sensitive HTML processing.
    """
    text = _HTML_TAG_PATTERN.sub(" ", text)
    return _html.unescape(text)

def fix_encoding(text: str) -> str:
    """Repair mojibake, smart quotes, and Unicode damage."""
    return ftfy.fix_text(text)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace and trim ends."""
    return _MULTI_WS.sub(" ", text).strip()


def anonymize_pii(text: str) -> str:
    """Replace PII with placeholder tokens."""
    out = text
    out = _EMAIL_PATTERN.sub(" <EMAIL> ", out)
    for pattern in _URL_PATTERNS:
        out = pattern.sub(" <URL> ", out)
    for pattern in _PHONE_PATTERNS:
        out = pattern.sub(" <PHONE> ", out)
    out = _MONEY_PATTERN.sub(" <MONEY> ", out)
    return normalize_whitespace(out)


def clean_text(text: str) -> str:
    """Full cleaning pipeline. Apply to every raw message."""
    if not isinstance(text, str):
        return ""
    text = fix_encoding(text)
    text = normalize_whitespace(text)
    text = anonymize_pii(text)
    return text


def is_valid_message(text: str, min_chars: int = 3) -> bool:
    """Filter messages too short to train on."""
    return isinstance(text, str) and len(text.strip()) >= min_chars
