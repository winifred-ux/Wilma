"""
Wilma -- HTML visualization of token attributions.

Design goals:
- Linear/Stripe-grade typography and spacing
- Both light and dark modes with manual toggle (and OS-default fallback)
- Subtle, restrained color usage; one accent
- Reading-document feel for the message body
- Tabular numerics, baseline-aligned signals table
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html as _html
import string
import sys
from pathlib import Path
from typing import Optional

from wilma.inference.explain import (
    DEFAULT_BINARY_MODEL,
    DEFAULT_MULTICLASS_MODEL,
    Explanation,
    WilmaExplainer,
    merge_subwords,
)


SIGNIFICANCE_THRESHOLD = 0.18


CSS = """
:root {
  --bg:        #fafafa;
  --surface:   #ffffff;
  --border:    #e8e8e8;
  --rule:      #f0f0f0;
  --ink:       #0a0a0a;
  --ink-2:     #525252;
  --ink-3:     #8a8a8a;
  --accent:    #1f4e79;
  --scam:      #c41e1e;
  --scam-bg:   rgba(196, 30, 30, 0.10);
  --scam-bg-2: rgba(196, 30, 30, 0.18);
  --legit:     #15803d;
  --legit-bg:  rgba(21, 128, 61, 0.10);
  --legit-bg-2:rgba(21, 128, 61, 0.18);
  --shadow:    0 1px 2px rgba(0,0,0,0.04);
}
[data-theme="dark"] {
  --bg:        #0a0a0a;
  --surface:   #141414;
  --border:    #262626;
  --rule:      #1f1f1f;
  --ink:       #f5f5f5;
  --ink-2:     #a3a3a3;
  --ink-3:     #6b6b6b;
  --accent:    #5fa3dc;
  --scam:      #f87171;
  --scam-bg:   rgba(248, 113, 113, 0.14);
  --scam-bg-2: rgba(248, 113, 113, 0.26);
  --legit:     #4ade80;
  --legit-bg:  rgba(74, 222, 128, 0.12);
  --legit-bg-2:rgba(74, 222, 128, 0.22);
  --shadow:    0 1px 2px rgba(0,0,0,0.5);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]):not([data-theme="dark"]) {
    --bg:        #0a0a0a;
    --surface:   #141414;
    --border:    #262626;
    --rule:      #1f1f1f;
    --ink:       #f5f5f5;
    --ink-2:     #a3a3a3;
    --ink-3:     #6b6b6b;
    --accent:    #5fa3dc;
    --scam:      #f87171;
    --scam-bg:   rgba(248, 113, 113, 0.14);
    --scam-bg-2: rgba(248, 113, 113, 0.26);
    --legit:     #4ade80;
    --legit-bg:  rgba(74, 222, 128, 0.12);
    --legit-bg-2:rgba(74, 222, 128, 0.22);
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-feature-settings: "ss01", "cv11", "tnum";
  background: var(--bg);
  color: var(--ink);
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  min-height: 100vh;
  padding: 64px 24px;
}
.card {
  position: relative;
  max-width: 740px;
  margin: 0 auto;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 56px 56px 40px;
  box-shadow: var(--shadow);
}
.toggle {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 36px;
  height: 36px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 120ms, border-color 120ms;
}
.toggle:hover { color: var(--ink); border-color: var(--ink-3); }
.toggle svg { width: 16px; height: 16px; }
[data-theme="dark"] .toggle .icon-sun,
:root:not([data-theme="light"]) .toggle .icon-sun { display: none; }
[data-theme="light"] .toggle .icon-moon { display: none; }
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) .toggle .icon-moon { display: none; }
  :root:not([data-theme="dark"]) .toggle .icon-sun { display: block; }
}

.kicker {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--ink-3);
  margin-bottom: 14px;
}
h1.verdict {
  margin: 0;
  font-size: 40px;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--ink);
}
.verdict.is-scam h1.verdict { color: var(--scam); }
.verdict.is-legit h1.verdict { color: var(--legit); }
.meta {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--ink-2);
}
.meta .dot { color: var(--ink-3); }
.meta .conf { font-variant-numeric: tabular-nums; font-weight: 500; color: var(--ink); }

.section-rule {
  border: none;
  border-top: 1px solid var(--rule);
  margin: 36px 0;
}

.message {
  position: relative;
  padding-left: 18px;
  border-left: 2px solid var(--border);
  font-size: 17px;
  line-height: 1.85;
  color: var(--ink);
  word-wrap: break-word;
}
.tok { transition: background 80ms; }
.tok.signal-mid {
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 4px;
}
.tok.signal-mid.pos { text-decoration-color: var(--scam); }
.tok.signal-mid.neg { text-decoration-color: var(--legit); }
.tok.signal-strong {
  padding: 1px 3px;
  border-radius: 3px;
  font-weight: 500;
}
.tok.signal-strong.pos { background: var(--scam-bg); color: var(--scam); }
.tok.signal-strong.neg { background: var(--legit-bg); color: var(--legit); }
.tok.signal-extreme {
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: 600;
}
.tok.signal-extreme.pos { background: var(--scam-bg-2); color: var(--scam); }
.tok.signal-extreme.neg { background: var(--legit-bg-2); color: var(--legit); }
.tok[data-score] { position: relative; cursor: default; }
.tok[data-score]:hover::after {
  content: attr(data-score);
  position: absolute;
  bottom: 130%;
  left: 50%;
  transform: translateX(-50%);
  background: var(--ink);
  color: var(--surface);
  padding: 4px 8px;
  border-radius: 4px;
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", monospace;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  pointer-events: none;
  z-index: 20;
  letter-spacing: 0;
}

.signals h2 {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--ink-3);
  margin: 0 0 18px;
}
.signal-list { display: flex; flex-direction: column; gap: 10px; }
.signal-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px minmax(120px, 180px);
  align-items: center;
  gap: 16px;
  font-size: 14px;
}
.signal-row .name {
  color: var(--ink);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.signal-row .score {
  font-family: ui-monospace, "SF Mono", "JetBrains Mono", monospace;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: right;
  color: var(--ink-2);
}
.signal-row .bar {
  background: var(--rule);
  border-radius: 999px;
  height: 4px;
  overflow: hidden;
}
.signal-row .bar > div {
  height: 100%;
  border-radius: 999px;
  transition: width 240ms cubic-bezier(0.2, 0.8, 0.2, 1);
}
.signal-row.pos .bar > div { background: var(--scam); }
.signal-row.neg .bar > div { background: var(--legit); }

footer {
  margin-top: 32px;
  padding-top: 18px;
  border-top: 1px solid var(--rule);
  font-size: 11px;
  color: var(--ink-3);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
footer .right {
  font-family: ui-monospace, "SF Mono", monospace;
  letter-spacing: 0;
}

@media (max-width: 640px) {
  body { padding: 24px 16px; }
  .card { padding: 32px 24px 28px; }
  h1.verdict { font-size: 30px; }
  .signal-row { grid-template-columns: 1fr 64px 100px; gap: 10px; }
}
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wilma — __VERDICT_TITLE__</title>
<link rel="preconnect" href="https://rsms.me/">
<link rel="stylesheet" href="https://rsms.me/inter/inter.css">
<style>__CSS__</style>
</head>
<body>
<main class="card __VERDICT_OUTER__">
  <button class="toggle" id="theme-toggle" aria-label="Toggle color theme">
    <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
    <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
  </button>

  <header>
    <div class="kicker">Wilma · Classification</div>
    <h1 class="verdict">__VERDICT_LABEL__</h1>
    <div class="meta">
      <span class="conf">__VERDICT_PROBA__</span>
      <span>confidence</span>
      <span class="dot">·</span>
      <span>__MODEL_LABEL__</span>
    </div>
  </header>

  <hr class="section-rule">

  <section class="message">__TOKEN_HTML__</section>

  <hr class="section-rule">

  <section class="signals">
    <h2>Top signals · Integrated Gradients</h2>
    <div class="signal-list">__TOP_ROWS__</div>
  </section>

  <footer>
    <span>Wilma — Watchful Intelligence for Linguistic Message Analysis</span>
    <span class="right">__TIMESTAMP__</span>
  </footer>
</main>

<script>
(function() {
  const root = document.documentElement;
  let stored = null;
  try { stored = localStorage.getItem('wilma-theme'); } catch (e) {}
  if (stored === 'dark' || stored === 'light') {
    root.setAttribute('data-theme', stored);
  }
  document.getElementById('theme-toggle').addEventListener('click', function() {
    const current = root.getAttribute('data-theme');
    const prefersDark = matchMedia('(prefers-color-scheme: dark)').matches;
    let next;
    if (current === 'dark') next = 'light';
    else if (current === 'light') next = 'dark';
    else next = prefersDark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('wilma-theme', next); } catch (e) {}
  });
})();
</script>
</body>
</html>
"""


def _is_punct(token: str) -> bool:
    return all(c in string.punctuation for c in token) and len(token) > 0


def _classify_score(score: float, max_abs: float) -> str:
    if max_abs <= 0:
        return ""
    intensity = abs(score) / max_abs
    if intensity < SIGNIFICANCE_THRESHOLD:
        return ""
    direction = "pos" if score > 0 else "neg"
    if intensity >= 0.78:
        return f"signal-extreme {direction}"
    if intensity >= 0.45:
        return f"signal-strong {direction}"
    return f"signal-mid {direction}"


def _render_token_html(tokens, scores):
    if not scores:
        return ""
    max_abs = max(abs(s) for s in scores) or 1.0
    parts = []
    rendered_count = 0
    for token, score in zip(tokens, scores):
        if token in ("[CLS]", "[SEP]", "[PAD]"):
            continue
        css_class = _classify_score(score, max_abs)
        safe_token = _html.escape(token)
        if css_class:
            span = f'<span class="tok {css_class}" data-score="{score:+.4f}">{safe_token}</span>'
        else:
            span = safe_token
        if rendered_count > 0 and not _is_punct(token):
            parts.append(" ")
        parts.append(span)
        rendered_count += 1
    return "".join(parts)


def _render_top_rows(top):
    if not top:
        return '<div class="signal-row"><div class="name">No tokens to show</div><div></div><div></div></div>'
    max_abs = max(abs(s) for _, s in top) or 1.0
    rows = []
    for token, score in top:
        bar_pct = int((abs(score) / max_abs) * 100)
        direction = "pos" if score > 0 else "neg"
        rows.append(
            f'<div class="signal-row {direction}">'
            f'<div class="name">{_html.escape(token)}</div>'
            f'<div class="score">{score:+.3f}</div>'
            f'<div class="bar"><div style="width:{bar_pct}%"></div></div>'
            f'</div>'
        )
    return "".join(rows)


def visualize_explanation(exp: Explanation, model_label: Optional[str] = None) -> str:
    merged_tokens, merged_scores = merge_subwords(exp.tokens, exp.attributions)

    title_label = exp.predicted_class.replace("_", " ").title()
    is_legit = exp.predicted_class == "legitimate"
    verdict_outer = "verdict is-legit" if is_legit else "verdict is-scam"
    verdict_proba = f"{exp.predicted_proba:.1%}"

    if model_label is None:
        model_label = "DistilBERT v1"

    timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    token_html = _render_token_html(merged_tokens, merged_scores)
    top_rows = _render_top_rows(exp.top(8))

    doc = HTML_TEMPLATE
    doc = doc.replace("__CSS__", CSS)
    doc = doc.replace("__VERDICT_TITLE__", _html.escape(title_label))
    doc = doc.replace("__VERDICT_OUTER__", verdict_outer)
    doc = doc.replace("__VERDICT_LABEL__", _html.escape(title_label))
    doc = doc.replace("__VERDICT_PROBA__", _html.escape(verdict_proba))
    doc = doc.replace("__MODEL_LABEL__", _html.escape(model_label))
    doc = doc.replace("__TOKEN_HTML__", token_html)
    doc = doc.replace("__TOP_ROWS__", top_rows)
    doc = doc.replace("__TIMESTAMP__", _html.escape(timestamp))
    return doc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Visualize a Wilma classification as HTML")
    parser.add_argument("text", help="Message text to classify and visualize")
    parser.add_argument("--multiclass", action="store_true", help="Use the multi-class model")
    parser.add_argument("-o", "--output", default="explanation.html",
                        help="Output HTML file path (default: explanation.html)")
    args = parser.parse_args(argv)

    if args.multiclass:
        model_path = DEFAULT_MULTICLASS_MODEL
        model_label = "DistilBERT v1 · multi-class"
    else:
        model_path = DEFAULT_BINARY_MODEL
        model_label = "DistilBERT v1 · binary"

    print(f"Loading model: {model_path.name}")
    explainer = WilmaExplainer(model_path)
    print("Computing explanation...")
    exp = explainer.explain(args.text)
    print(f"  Verdict: {exp.predicted_class} ({exp.predicted_proba:.1%})")

    html_doc = visualize_explanation(exp, model_label=model_label)
    out_path = Path(args.output)
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"\nHTML written to: {out_path.absolute()}")
    print(f"Open with: open {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
