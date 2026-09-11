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
---

## Length experiment: why the Nigerian SMS numbers are what they are

**Date:** September 2026
**Script:** `scripts/length_experiment.py`
**Data:** `data/eval/length_experiment.csv`

### Design

Eight known scam types were written three times each: a short SMS-length
version, a medium version, and a long formal version. The fraudulent
content is identical across all three variants. Only length and register
change. If the model were reading fraud semantics, detection should be
roughly flat across variants. If it were reading document shape, detection
should climb with length.

The eight scams: promo-draw winnings, BVN blocking, 419 barrister
inheritance, family-impersonation ("hi mum"), forex investment returns,
customs clearance fee, work-from-home recruitment, and OTP harvesting.

### Result

| Variant | Mean length | Detected | Mean confidence |
|---|---|---|---|
| short  | 60 chars  | 0/8 (0%)  | 0.981 |
| medium | 167 chars | 4/8 (50%) | 0.999 |
| long   | 932 chars | 7/8 (88%) | 0.996 |

Detection rises from 0% to 88% purely as a function of length, with the
fraudulent content held constant.

Representative case, the OTP harvesting scam:

- 62 chars: `legitimate` at 0.883
- 184 chars: `scam` at 0.998
- 966 chars: `scam` at 1.000

And the 419 barrister letter, the most recognisable scam format in the
country:

- short: `legitimate` at 1.000
- medium: `legitimate` at 1.000
- long: `scam` at 1.000

### Interpretation

This confirms distribution shift and identifies its mechanism precisely.
The training corpora (Enron, SpamAssassin, Kaggle fraud) are long-form
English email. The model learned that long, formal, letter-shaped
documents are fraudulent and that short informal text is not. It is
classifying document shape, not fraud.

This explains the gap between 99.24% accuracy on the held-out test set and
80.00% on Nigerian SMS. Both numbers are correct. The test set resembles
the training data; Nigerian SMS does not.

### Commercial consequence

Nigerian fraud arrives predominantly by SMS and WhatsApp, and those
messages are short. The model scores 0% in exactly the regime the product
is intended to serve. The headline accuracy figure is real but does not
describe performance on the target use case.

The confidence score is worse than uncalibrated. It returned 1.000
`legitimate` on eight live scams. It cannot currently be used as a
decision threshold by any customer.

### What this changes

The fix is now specific rather than general. The model does not need more
data, it needs short data. Priorities in order:

1. Fine tune on short-message corpora, not email corpora.
2. Collect several hundred real Nigerian SMS from actual phones, scam and
   legitimate, preserving original length and register.
3. Hold transactional formats (OTP alerts, debit alerts, recharge
   confirmations) out as an explicit negative class, since these are the
   highest-cost false positives for a bank.
4. Re-run this length experiment after fine tuning. Flat detection across
   the three variants is the pass condition.
5. Recalibrate confidence and re-evaluate before quoting any threshold to
   a customer.

Until item 4 passes, Wilma should not be sold as an SMS fraud detector.

---

## v2: fine tuned on short-message data

**Date:** 11 September 2026
**Model:** `models/distilbert_v2`, DistilBERT base, same architecture as v1
so the data is the only variable
**Training:** 13,704 messages (11,404 scam from Smishtank, 2,300 legitimate
from ExAIS), class weights 2.979 / 0.601, 3 epochs, max length 128
**Evaluation:** `scripts/eval_local.py`

### Held out test set

accuracy 0.9813, precision 0.9896, recall 0.9882, F1 0.9889.
1,424 caught, 15 false alarms, 17 missed.

As with v1, this number describes data shaped like the training data and
should never be quoted alone.

### Length experiment — PASSED

| Variant | Mean length | v1 detected | v2 detected | v2 mean conf |
|---|---|---|---|---|
| short  | 60 chars  | 0/8 (0%)  | **6/8 (75%)** | 0.909 |
| medium | 167 chars | 4/8 (50%) | 7/8 (88%) | 0.929 |
| long   | 932 chars | 7/8 (88%) | 7/8 (88%) | 0.956 |

Detection is now near flat across length with the fraudulent content held
constant. The model responds to fraud semantics rather than document shape.
This was the stated pass condition and it is met.

### Nigerian SMS evaluation — REGRESSED

| | v1 | v2 |
|---|---|---|
| accuracy | 0.8000 | **0.6250** |
| precision | 0.8333 | 0.6316 |
| recall | 0.7500 | 0.6000 |
| F1 | 0.7895 | 0.6154 |

12 caught, 7 false alarms, 8 missed, 13 correct legitimate.

### Why, and it is not mysterious

The mistakes split into two clean groups.

**Every missed scam is Nigerian in a way the training data is not.**

- won N2,000,000 in our promo, send your account details
- pending transfer of N450,000, confirm your account number
- package on hold at customs, pay N12,500 clearance
- MTN line has won N500,000, dial a USSD code
- loan approved, send your BVN and card details
- you have been shortlisted, pay N7,500 for your screening form
- double your money in 7 days, chat me on WhatsApp

The fraud class is Indian, American and European smishing. It contains no
naira promo scams, no BVN loan bait, no screening-fee job scam. These could
not have been caught.

**Every false alarm is transactional or ordinary correspondence.**

- a genuine OTP
- a debit alert with a merchant and balance
- a shipping notification
- a payment receipt confirmation
- a colleague saying they had emailed documents

The training set contains 10,490 banking phishes and 1,675 delivery scams
against 2,300 legitimate messages, most of them 2014 telco traffic and
personal chat. The model learned that banking and delivery language signals
fraud. Real OTPs and delivery notices are the collateral.

### Decision

**v2 is not deployed.** The live Space continues to serve v1. v2 is worse on
the only evaluation that reflects the target market, and its false alarms
land on OTPs and debit alerts, the most commercially damaging error for a
bank customer. v2 stays local until it beats v1 on the Nigerian set.

### What this changes about collection

The target is no longer "300 Nigerian SMS". Two specific categories, each
measured as the cause of one failure group:

1. **Nigerian fraud SMS.** Promo wins in naira, BVN and loan bait, screening
   and clearance fee scams, USSD claim codes, WhatsApp investment pitches.
   Target 300 or more.
2. **Modern legitimate transactional messages.** OTPs, debit and credit
   alerts, delivery and dispatch notices, payment receipts, appointment
   confirmations. Target 300 or more. These are held-out negatives that
   defend precision.

The evaluation set is 40 messages, so these figures carry wide error bars.
Growing it to several hundred real messages is part of the same collection
effort and should happen before any figure is quoted to a customer.

### Standing position

The 99.24% from v1 and the 98.13% from v2 both describe held out data drawn
from the same distribution as their training sets. Neither describes
Nigerian SMS. Both must always be quoted alongside the Nigerian figure.
