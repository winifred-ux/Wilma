# Wilma training data

Built by `scripts/build_dataset.py`. Splits in `data/processed/`.

## Composition

| Split | Rows | Scam | Legitimate | Median chars |
|---|---|---|---|---|
| train | 13,704 | 11,404 | 2,300 | 125 |
| val | 1,713 | 1,420 | 293 | 123 |
| test | 1,714 | 1,441 | 273 | 123 |

17,131 unique messages across 15,569 template groups.

## Sources

**Smishtank (Smishing-Dataset-IMC25)** — real user-reported SMS phishing,
CC BY 4.0, attribution required. 33,869 reports filtered to 20,624 English,
deduplicated to 14,238. Rows labelled `scam_type: spam` were dropped, since
those are bulk marketing rather than fraud.

**ExAIS SMS Spam Dataset** (FUNAAB, Nigeria, 2014–2016) — 5,240 messages from
20 people. Used for the legitimate class only. No licence is stated in the
repository, so written permission should be obtained before commercial use.

## Why ExAIS provides only negatives

ExAIS labels "spam" as unsolicited bulk messaging, not fraud. Of roughly
1,425 spam rows, only 27 are actual fraud. 488 are telco marketing and 18
are genuine bank alerts mislabelled as spam. A manual review of the 29
highest fraud-scoring remaining rows found zero fraud.

Training on its labels unexamined would teach the model that MTN and Glo
promotions and real bank alerts are scams — the same false positive that
broke the Nigerian SMS evaluation.

## Leakage controls

**Placeholder tokens.** The two corpora redacted differently. Everything was
normalised to five tokens present on both sides: `<ACCT>`, `<DATE>`,
`<PHONE>`, `<EMAIL>`, `<URL>`. Tokens a regex cannot reproduce on the ExAIS
side (`<NAME>`, `<LOCATION>`, `<NRP>`) were stripped rather than kept on one
side only. Verified: no token appears in one class and not the other.

**Label text leakage.** 98 ExAIS rows carried the literal word `ham` or
`spam` at the end of the message text, a parsing artefact. Stripped.

**Template grouping.** Near-duplicate messages are grouped by a normalised
template key and assigned to a single split, so a scam blast reported many
times cannot appear in both train and test.

**Evaluation set.** `data/eval/nigerian_sms.csv` is excluded from all
splits. It remains the only honest judge of Nigerian performance.

## Known limitations

- **No Nigerian fraud.** The fraud class is Indian, American and European
  smishing. Nigerian fraud idiom is absent and must be collected.
- **Brand skew.** `sbi` (State Bank of India) appears in 10.7% of scams and
  0% of legitimate messages. The model may learn that foreign bank names
  mean fraud and Nigerian ones mean safe, which is backwards for this
  market, where scams impersonate Zenith, GTB and Access.
- **Class imbalance.** 5:1 scam to legitimate. Handled with class weights
  (legitimate 2.979, scam 0.601) rather than by padding the legitimate class
  with foreign chat data, which would have taught the model that informal
  means safe and formal means fraud.
- **Age.** ExAIS is 2014–2016. Transactional formats are stable over that
  period; scam tactics are not.

## Pass condition

Re-run `scripts/length_experiment.py` after fine tuning. Detection must be
flat across short, medium and long variants of the same scam. The pre-tuning
baseline was 0/8, 4/8, 7/8.
