# Evaluation

## Summary

Wilma scores 99.24% accuracy on its held out test set, drawn from the same
public corpora it was trained on. On a hand built set of Nigerian SMS
messages it scores **80.00%**.

That gap is the most important number in this project. It is recorded here
rather than hidden, because the SMS figure is the one that reflects the
intended use.

## Reported metrics

### Public corpora, held out test split

| Model | F1 | Accuracy |
|---|---:|---:|
| TF-IDF + Logistic Regression | 0.9837 | 98.43% |
| fastText | 0.9835 | 98.40% |
| DistilBERT binary | 0.9921 | 99.24% |
| DistilBERT 4-class | 0.9761 macro | 98.22% |

Training set: 39,465 messages merged from Enron spam, SpamAssassin, an SMS
spam corpus and a Kaggle fraud set.

### Nigerian SMS set, September 2026

40 messages, 20 scam and 20 legitimate, written to reflect message formats
commonly reported in Nigeria. Run against the live API.

| Metric | Value |
|---|---:|
| Accuracy | 80.00% |
| Precision | 83.33% |
| Recall | 75.00% |
| F1 | 0.7895 |

Confusion matrix:

|  | predicted scam | predicted legitimate |
|---|---:|---:|
| **actual scam** | 15 | 5 |
| **actual legitimate** | 3 | 17 |

## Failure analysis

### Missed scams (5)

The model called these legitimate, every one at 1.000 confidence:

- NIN update demand threatening SIM blockage
- Advance fee 419 letter, the barrister and inheritance format
- Subscription renewal asking for card details
- Romance approach from a claimed widow with funds
- Account review request asking for full card number and expiry

The 419 letter is the significant one. That format is heavily represented
in the training data. Failing it in short SMS form points at the model
having learned document shape rather than fraud semantics.

### False alarms (3)

The model called these scams, at 0.975 to 0.999 confidence:

- An OTP delivery message
- A routine debit alert with a naira amount and balance
- A data recharge confirmation

These are ordinary transactional messages that Nigerian banks and telcos
send constantly. Flagging them would make the product unusable for a bank,
since it would be flagging that bank's own traffic.

### Confidence is not calibrated

Every misclassification above was made at or near total confidence. The
score currently carries no usable signal about how likely the model is to
be right, so it cannot be used as a threshold to trade recall against
precision.

## Interpretation

The training data is long form email, largely American and largely from an
earlier era, plus SMS spam that is mostly UK and US in origin. Nigerian
transactional SMS is short, contains naira amounts, capitals and urgency
markers, all of which correlate with scam in that training data.

The most likely explanation is distribution shift. The model appears to key
on document length, formatting and vocabulary characteristic of the
training corpora rather than on the substance of fraud. Those signals are
absent in a one line SMS.

## What this means

Wilma should not currently be sold as an SMS fraud detector for Nigerian
institutions. The recall is too low to catch fraud reliably, and the false
positive rate on transactional messages is high enough to be disqualifying
on its own.

The headline 99.24% is accurate for the public corpora and should always be
quoted alongside the SMS figure.

## Next steps

1. Grow the Nigerian SMS set to several hundred real messages, collected
   from actual phones rather than written by hand
2. Fine tune on short message data rather than relying on the email trained
   model
3. Hold transactional message formats out explicitly, since bank alerts,
   OTPs and recharge confirmations are the highest cost false positives
4. Investigate calibration, so the confidence score becomes usable
5. Re-run this evaluation after each change and record the result here

## Reproducing

```bash
export WILMA_API_KEY=your_key
python3 scripts/eval_nigerian_sms.py
```

Test set lives at `data/eval/nigerian_sms.csv`.