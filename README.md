# Wilma

> **Watchful Intelligence for Linguistic Message Analysis**

AI-powered scam detection API for SMS, email, and chat messages. Built with a fine-tuned multilingual DistilBERT transformer, optimised for the linguistic and cultural patterns of scams in Nigeria and across Sub-Saharan Africa.

---

## Status

🚧 **Active development — Version 1 (text classification layer)**

Wilma is being built in phases. Version 1 (in progress) delivers a production-grade text-based scam detection API. Future versions extend the system into voice, behavioural, and location-based fraud signals.

## Vision

Wilma is the text-classification foundation of a multi-layer fraud and scam prevention system. The complete platform integrates four intelligence layers feeding into a unified risk score:

1. **Text layer** *(V1 — current)* — DistilBERT-based scam classification for messages
2. **Voice layer** *(future)* — deepfake and vishing detection on call audio
3. **Behavioural layer** *(future)* — anomaly detection over user event streams
4. **Location layer** *(future)* — geo-velocity and high-risk-region monitoring

## V1 Capabilities

- Binary and multi-class scam classification across seven categories: phishing, 419 / advance-fee fraud, fake-OTP, impersonation, romance, fake-loan, and cryptocurrency scams
- Multilingual support including English, Nigerian Pidgin, and code-switched text
- Token-level explainability — every classification comes with the words that triggered it
- REST API with API-key authentication and rate limiting
- Sub-150ms p95 inference latency on commodity CPU hardware
- User feedback endpoint to power continuous improvement

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11 |
| ML Framework | PyTorch + Hugging Face Transformers |
| Base Model | distilbert-base-multilingual-cased |
| API Framework | FastAPI + Pydantic + Uvicorn |
| Inference Runtime | ONNX Runtime |
| Experiment Tracking | Weights & Biases |
| Containerization | Docker |
| Testing | pytest |

## Repository Structure

## Getting Started (Development)

### Prerequisites

- Python 3.11
- Git
- macOS, Linux, or WSL on Windows

### Setup

```bash
# Clone the repository
git clone https://github.com/winifred-ux/Wilma.git wilma
cd wilma

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Roadmap

- [x] Project foundation: repository, environment, structure
- [ ] Week 1 — Data acquisition and cleaning pipeline
- [ ] Week 2 — Baseline classifiers (Logistic Regression, fastText)
- [ ] Week 3 — DistilBERT fine-tuning (binary)
- [ ] Week 4 — Multi-class classification and explainability
- [ ] Week 5 — REST API development
- [ ] Week 6 — Containerization and public deployment
- [ ] Week 7 — Production hardening (auth, rate limiting, CI)
- [ ] Week 8 — Comprehensive evaluation
- [ ] Week 9 — Documentation and academic report
- [ ] Week 10 — Launch and industry outreach

## License

This project is released under the [MIT License](LICENSE).

## Author

Built by Winifred Ajah as a final year project and venture initiative.