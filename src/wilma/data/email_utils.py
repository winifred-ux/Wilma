"""
Wilma — email parsing utilities.

Helpers for extracting clean text from RFC-822 email messages.
Used by the SpamAssassin and Kaggle 419 cleaners.

Email handling is messier than it looks: mixed encodings, multipart
structures, base64 transfer encodings, HTML bodies. This module
hides that complexity behind extract_subject_and_body().
"""

from __future__ import annotations

from email.message import Message

from wilma.data.cleaners import strip_html


def _decode_part(part: Message) -> str:
    """Decode a single email part to string, handling encodings safely."""
    payload = part.get_payload(decode=True)
    if payload is None:
        sub = part.get_payload()
        return sub if isinstance(sub, str) else ""
    if isinstance(payload, bytes):
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return payload.decode("utf-8", errors="replace")
    return str(payload)


def extract_email_body(msg: Message) -> str:
    """Return the best-effort plain-text body of an email message.

    Prefers text/plain parts; falls back to text/html with tags stripped.
    """
    if msg.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for part in msg.walk():
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain":
                plain_parts.append(_decode_part(part))
            elif ctype == "text/html":
                html_parts.append(_decode_part(part))
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return strip_html("\n".join(html_parts))
        return ""

    payload = _decode_part(msg)
    if msg.get_content_type() == "text/html":
        return strip_html(payload)
    return payload


def extract_subject_and_body(msg: Message) -> str:
    """Combine Subject header and body into one text field."""
    subject = msg.get("Subject", "") or ""
    if isinstance(subject, str):
        subject = subject.strip()
    body = extract_email_body(msg).strip()
    parts: list[str] = []
    if subject:
        parts.append(subject)
    if body:
        parts.append(body)
    return "\n\n".join(parts)
