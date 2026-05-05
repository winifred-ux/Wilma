# Wilma — Raw Datasets

This folder holds the foundational public scam/spam datasets used for Wilma V1 training.

**Do not edit files here directly.** All cleaning happens in `data/interim/` and `data/processed/`. Files in this folder are gitignored — to reproduce, run `python scripts/download_data.py`.

## Datasets

### 1. UCI SMS Spam Collection (`sms_spam/`)

- **Source:** UCI Machine Learning Repository — https://archive.ics.uci.edu/dataset/228/sms+spam+collection
- **Size:** 5,574 SMS messages (English)
- **Labels:** `ham` (legitimate) / `spam`
- **License:** Public — academic use permitted
- **Why it's here:** Industry-standard benchmark for SMS spam classification. Provides our binary baseline.

### 2. Enron-Spam (`enron_spam/`)

- **Source:** Preprocessed mirror by MWiechmann — https://github.com/MWiechmann/enron_spam_data
- **Size:** ~33,000 emails
- **Labels:** `ham` / `spam`
- **License:** Original Enron dataset is public domain (released by FERC during legal proceedings)
- **Why it's here:** Large volume of legitimate corporate emails plus spam, anchoring the "legitimate" class.

### 3. SpamAssassin Public Corpus (`spamassassin/`)

- **Source:** Apache SpamAssassin — https://spamassassin.apache.org/old/publiccorpus/
- **Size:** ~500 spam emails
- **Labels:** All spam
- **License:** Public corpus, redistribution permitted
- **Why it's here:** Diverse phishing-adjacent samples, complements other sources.

### 4. Kaggle Fraudulent Email Corpus (`kaggle_fraud_email/`)

- **Source:** Kaggle (rtatman) — https://www.kaggle.com/datasets/rtatman/fraudulent-email-corpus
- **Size:** ~3,900 fraudulent emails
- **Labels:** All fraud (419 / advance-fee scams)
- **License:** CC-BY-SA-4.0
- **Why it's here:** This is the Nigeria-specific gold mine. Classic 419 scam patterns in their native form. Our competitive edge over Western fraud detection systems comes from training on this kind of culturally and linguistically specific data.

## Reproducibility

To regenerate this folder from scratch:

```bash
source .venv/bin/activate
python scripts/download_data.py
```

The script is idempotent — it skips datasets that are already present.

## Local Data Collection (Future)

Beyond these public corpora, Wilma V1 will be augmented with locally-sourced Nigerian scam SMS examples collected from the project author's own messages, contributions from trusted contacts, and publicly archived examples on scam-tracking forums. That collection lives in `local_nigerian_sms/` (added in Week 1, Day 5).