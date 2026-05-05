"""Tests for src/wilma/data/cleaners.py."""

from wilma.data.cleaners import (
    anonymize_pii,
    clean_text,
    fix_encoding,
    is_valid_message,
    normalize_whitespace,
    strip_html,
)


def test_normalize_whitespace_collapses_runs() -> None:
    assert normalize_whitespace("hello    world\t\n") == "hello world"


def test_fix_encoding_repairs_mojibake() -> None:
    assert fix_encoding("itâ€™s a scam") == "it's a scam"


def test_anonymize_pii_replaces_nigerian_phone() -> None:
    out = anonymize_pii("Call me on 08012345678 now")
    assert "<PHONE>" in out
    assert "08012345678" not in out


def test_anonymize_pii_replaces_url_and_email() -> None:
    raw = "Visit http://scam.example.com or email me at fake@example.org"
    out = anonymize_pii(raw)
    assert "<URL>" in out
    assert "<EMAIL>" in out
    assert "scam.example.com" not in out
    assert "fake@example.org" not in out


def test_clean_text_full_pipeline() -> None:
    raw = "  CONGRATS!!!  You won  N500,000.  Call 08123456789  "
    out = clean_text(raw)
    assert "<PHONE>" in out
    assert "<MONEY>" in out
    assert "  " not in out


def test_is_valid_message_rejects_too_short() -> None:
    assert is_valid_message("hello world")
    assert not is_valid_message("hi")
    assert not is_valid_message("")
    assert not is_valid_message(None)  # type: ignore[arg-type]

def test_strip_html_removes_tags() -> None:
    out = strip_html("<p>Hello <b>world</b></p>")
    assert "Hello" in out
    assert "world" in out
    assert "<" not in out
    assert ">" not in out


def test_strip_html_decodes_entities() -> None:
    assert "&" in strip_html("Tom &amp; Jerry")
    assert strip_html("Price: &#36;100") == "Price: $100"

