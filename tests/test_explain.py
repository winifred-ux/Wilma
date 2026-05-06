"""Smoke test for the WilmaExplainer.

These tests don't assert specific attribution scores (they would be
brittle to retraining). They check the explainer runs end-to-end and
produces a structurally valid Explanation object.
"""

from pathlib import Path

import pytest

from wilma.inference.explain import WilmaExplainer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BINARY_MODEL = PROJECT_ROOT / "models" / "distilbert_v1"


def _model_available() -> bool:
    return BINARY_MODEL.exists() and (BINARY_MODEL / "config.json").exists()


@pytest.mark.skipif(not _model_available(), reason="Binary model not trained yet")
def test_explainer_returns_structured_output() -> None:
    explainer = WilmaExplainer(BINARY_MODEL)
    exp = explainer.explain("URGENT business assistance, transfer needed")

    # Structural checks only -- no specific scores
    assert exp.predicted_class in ("legitimate", "scam")
    assert 0.0 <= exp.predicted_proba <= 1.0
    assert len(exp.tokens) > 0
    assert len(exp.tokens) == len(exp.attributions)

    top = exp.top(5)
    assert len(top) <= 5
    assert all(isinstance(t, str) and isinstance(s, float) for t, s in top)


@pytest.mark.skipif(not _model_available(), reason="Binary model not trained yet")
def test_subword_merging() -> None:
    """Top tokens should be whole words (no ## prefixes)."""
    explainer = WilmaExplainer(BINARY_MODEL)
    exp = explainer.explain("URGENT BUSINESS ASSISTANCE")
    for token, _ in exp.top(10):
        assert not token.startswith("##"), f"unmerged subword in top: {token}"
