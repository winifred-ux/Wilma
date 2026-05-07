---
title: Wilma
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI fraud detection.
---

# Wilma — AI fraud detection

Wilma classifies SMS, email, and chat messages as scam or legitimate
in real time. Trained on 39,465 cleaned messages with a focus on
Nigerian advance-fee fraud patterns.

## Headline metrics

| Model | F1 (test) | Accuracy | Notes |
|---|---:|---:|---|
| TF-IDF + Logistic Regression | 0.9837 | 98.43% | Baseline |
| fastText | 0.9835 | 98.40% | Baseline |
| **DistilBERT (binary)** | **0.9921** | 99.24% | Production model |
| **DistilBERT (4-class)** | **0.9761 macro** | 98.22% | Categorizes scam type |

## Endpoints

- `POST /classify` — single message
- `POST /classify/batch` — up to 50 messages
- `GET /health` — health check
- `GET /docs` — interactive Swagger UI

## Example

```bash
curl -X POST https://winifred12-wilma.hf.space/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "URGENT BUSINESS ASSISTANCE: I need to transfer 25 million dollars"}'
```

```json
{
  "verdict": "scam",
  "confidence": 0.9998,
  "is_scam": true,
  "model": "DistilBERT v1 binary",
  "latency_ms": 87.3,
  "probabilities": {"legitimate": 0.0002, "scam": 0.9998}
}
```

## Categories (multi-class)

`legitimate`, `advance_fee_419`, `commercial_spam`, `scam_other`.

## Source code

[https://github.com/winifred-ux/Wilma](https://github.com/winifred-ux/Wilma)
