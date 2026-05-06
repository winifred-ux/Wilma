"""
Wilma -- token-level explainability via Integrated Gradients.

Given a trained DistilBERT classifier and an input message, produces
per-token attribution scores indicating each token's contribution to
the predicted class.

Implementation uses Captum's LayerIntegratedGradients applied to the
embedding layer, with a 50-step integration and a zero-embedding
baseline (Sundararajan et al., 2017).

Output format:
    {
        "predicted_class": "scam" | "advance_fee_419" | ...,
        "predicted_proba": 0.9876,
        "tokens": ["urgent", "business", ...],
        "attributions": [0.42, 0.38, ...],
        "top_tokens": [("urgent", 0.42), ("business", 0.38), ...],
    }

Run as a CLI:
    python -m wilma.inference.explain "URGENT BUSINESS ASSISTANCE"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from captum.attr import LayerIntegratedGradients
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def merge_subwords(tokens, scores):
    """Merge BERT-style subword tokens (##xyz) into whole words by summing their scores."""
    merged_tokens = []
    merged_scores = []
    for tok, sc in zip(tokens, scores):
        if tok.startswith("##") and merged_tokens:
            merged_tokens[-1] = merged_tokens[-1] + tok[2:]
            merged_scores[-1] = merged_scores[-1] + sc
        else:
            merged_tokens.append(tok)
            merged_scores.append(sc)
    return merged_tokens, merged_scores

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BINARY_MODEL = PROJECT_ROOT / "models" / "distilbert_v1"
DEFAULT_MULTICLASS_MODEL = PROJECT_ROOT / "models" / "distilbert_v1_multiclass"


@dataclass
class Explanation:
    predicted_class: str
    predicted_proba: float
    tokens: list[str]
    attributions: list[float]

    def top(self, k: int = 10) -> list[tuple[str, float]]:
        """Return the top-k tokens by absolute attribution, with subwords merged into whole words."""
        merged_tokens, merged_scores = merge_subwords(self.tokens, self.attributions)
        pairs = list(zip(merged_tokens, merged_scores))
        pairs = [(t, a) for t, a in pairs if t not in ("[CLS]", "[SEP]", "[PAD]")]
        pairs.sort(key=lambda x: abs(x[1]), reverse=True)
        return pairs[:k]


class WilmaExplainer:
    """Wraps a trained DistilBERT classifier with Integrated Gradients."""

    def __init__(self, model_path: Path, device: Optional[str] = None) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
        if device is None:
            # Captum Integrated Gradients uses float64 internally,
            # which MPS does not support. Default to CPU for explanations.
            # CUDA supports float64 fine. CPU is slower but correct.
            if torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"
        self.device = torch.device(device)
        self.model.to(self.device).eval()

        # The DistilBERT embedding layer name; Captum hooks here for IG.
        self.embedding_layer = self.model.distilbert.embeddings
        self.lig = LayerIntegratedGradients(self._forward_logits, self.embedding_layer)

        # Build a stable id2label map
        self.id2label = self.model.config.id2label

    def _forward_logits(self, input_ids, attention_mask):
        return self.model(input_ids=input_ids, attention_mask=attention_mask).logits

    @torch.no_grad()
    def predict(self, text: str, max_length: int = 256) -> tuple[int, float, dict]:
        """Return (predicted_class_id, predicted_proba, encoding_dict)."""
        enc = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
            padding=False,
        ).to(self.device)
        logits = self.model(**enc).logits
        probs = torch.softmax(logits, dim=-1).squeeze(0)
        cls_id = int(probs.argmax().item())
        proba = float(probs[cls_id].item())
        return cls_id, proba, enc

    def explain(
        self,
        text: str,
        target_class: Optional[int] = None,
        n_steps: int = 50,
        max_length: int = 256,
    ) -> Explanation:
        """Compute token attributions for the given text.

        target_class: which class to attribute toward. Defaults to the
                      predicted class (most useful interpretation).
        n_steps:      number of integration steps. 50 is a standard default.
        """
        cls_id, proba, enc = self.predict(text, max_length=max_length)
        if target_class is None:
            target_class = cls_id

        # Captum needs explicit input + baseline tensors.
        input_ids = enc["input_ids"]
        attention_mask = enc["attention_mask"]
        baseline_ids = torch.zeros_like(input_ids)

        attributions, _delta = self.lig.attribute(
            inputs=input_ids,
            baselines=baseline_ids,
            additional_forward_args=(attention_mask,),
            target=target_class,
            n_steps=n_steps,
            return_convergence_delta=True,
        )

        # Sum across embedding dim and normalize by the L2 norm
        token_attrs = attributions.sum(dim=-1).squeeze(0)
        token_attrs = token_attrs / (token_attrs.norm() + 1e-12)
        token_attrs = token_attrs.detach().cpu().tolist()

        tokens = self.tokenizer.convert_ids_to_tokens(input_ids.squeeze(0).tolist())

        return Explanation(
            predicted_class=self.id2label[cls_id],
            predicted_proba=proba,
            tokens=tokens,
            attributions=token_attrs,
        )


def _print_explanation(exp: Explanation, top_k: int = 10) -> None:
    print(f"  Predicted class: {exp.predicted_class}  ({exp.predicted_proba:.1%})")
    print(f"  Top {top_k} influential tokens:")
    for token, score in exp.top(top_k):
        bar = "+" * int(abs(score) * 30)
        sign = "+" if score >= 0 else "-"
        print(f"    {sign} {token:20s} {score:+.4f}  {bar}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python -m wilma.inference.explain <text> [--multiclass]")
        return 1
    text = argv[1]
    use_multiclass = "--multiclass" in argv
    model_path = DEFAULT_MULTICLASS_MODEL if use_multiclass else DEFAULT_BINARY_MODEL

    print(f"Loading model from {model_path.name}...")
    explainer = WilmaExplainer(model_path)

    print(f"\nInput: {text}\n")
    exp = explainer.explain(text)
    _print_explanation(exp)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
