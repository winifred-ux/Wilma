# Wilma — Processed Datasets

Final unified-schema, train/val/test-split datasets ready for model training.

**These files are gitignored** — to regenerate, run the full pipeline:

```bash
python scripts/download_data.py
python -m wilma.data.clean_sms_spam
python -m wilma.data.clean_enron_spam
python -m wilma.data.clean_spamassassin
python -m wilma.data.clean_kaggle_fraud
python -m wilma.data.merge_datasets
```

## Files

| File | Rows | Purpose |
|------|-----:|---------|
| `wilma_v1_train.csv` | ~31,500 | Model training |
| `wilma_v1_val.csv`   |  ~3,950 | Hyperparameter tuning, early stopping |
| `wilma_v1_test.csv`  |  ~3,950 | Final evaluation only — never trained on |
| `wilma_v1_full.csv`  | ~39,500 | Combined dataset (for re-splitting if needed) |

## Schema

Every row has these columns:

| Column     | Type | Description |
|------------|------|-------------|
| `id`       | str  | Stable per-row id (`<source>_<hash>`) |
| `text`     | str  | Cleaned, anonymized message text |
| `label`    | str  | Binary: `legitimate` or `scam` |
| `category` | str  | Multi-class: `legitimate`, `advance_fee_419`, `scam_other`, etc. |
| `source`   | str  | Originating dataset (`uci_sms_spam`, `enron_spam`, etc.) |
| `language` | str  | ISO 639-1 code, or `und` if undetermined |
| `char_len` | int  | Character length of cleaned text |
| `raw_hash` | str  | SHA-1 of original raw text (provenance + dedup) |

## Anonymization

All messages have been processed to replace personally identifiable
information with placeholder tokens before being saved:

- Phone numbers → `<PHONE>`
- Email addresses → `<EMAIL>`
- URLs → `<URL>`
- Money amounts → `<MONEY>`

This is required for NDPR / GDPR compliance and improves model
quality by forcing the model to learn linguistic patterns rather
than memorize specific identifiers.

## Reproducibility

The split uses `random_state=42` and is stratified by `label`,
ensuring identical train/val/test partitioning across reruns.
