# Nigerian SMS collection guide

Target: 300 messages minimum, roughly balanced. 150 scam, 150 legitimate.
Below 200 total the fine tune will not hold.

## Where messages go

`data/collected/messages.csv` — copy `messages_template.csv` to start it.

## Columns

| Column | What goes in it |
|---|---|
| `id` | `m0001`, `m0002`, ... sequential, never reused |
| `text` | The message, redacted (see below), in double quotes |
| `label` | `scam` or `legitimate`. Nothing else. |
| `subtype` | From the lists below |
| `source` | `own_phone`, `sister`, `partner`, `friend`, `family`, `public` |
| `received` | `YYYY-MM-DD`, approximate is fine, blank if unknown |
| `notes` | Anything odd. Optional. |

## Redaction — do this before saving

Nigerian data protection law applies once real people's messages are
stored, and a bank will ask. Replace, consistently, in BOTH classes:

- Account numbers -> `<ACCT>`
- Phone numbers -> `<PHONE>`
- Personal names -> `<NAME>`
- OTP / verification codes -> `<CODE>`
- Email addresses -> `<EMAIL>`
- URLs -> `<URL>`

Keep everything else exactly as written. **Do not fix spelling, do not fix
grammar, do not tidy the casing, do not expand abbreviations.** The broken
register is the signal. A cleaned-up scam message is a different message.

Keep amounts, bank names, merchant names and dates as they are. Those
carry real signal and are not personal data.

Applying redaction to only one class teaches the model to detect angle
brackets. Both classes, always.

## Scam subtypes

- `promo_win` — you have won, claim your prize
- `bank_phish` — BVN blocked, account restricted, verify now
- `otp_harvest` — send us the code we just sent you
- `419_inheritance` — barrister, late client, next of kin
- `impersonation` — hi mum, new number, send money
- `investment` — forex, crypto, guaranteed returns
- `delivery_fee` — parcel held, pay clearance
- `job_offer` — work from home, earn daily, no experience
- `loan_bait` — instant loan, no collateral, send fee first
- `other_scam`

## Legitimate subtypes

These matter as much as the scams. Every one of them is a message a bank
cannot afford Wilma to flag.

- `otp` — genuine verification codes
- `debit_alert` / `credit_alert` — genuine transaction alerts
- `recharge` — airtime and data confirmations
- `delivery_notice` — genuine dispatch and delivery updates
- `appointment` — reminders, bookings, confirmations
- `promo_marketing` — genuine marketing from real companies (MTN,
  Jumia, your bank). These are the hardest negatives. Collect plenty.
- `personal` — ordinary messages from real people
- `other_legit`

## Collection notes

- Short messages are the whole point. If a message is over 400 characters
  it is probably email-shaped and less useful. Collect it, but do not let
  long ones dominate.
- Duplicates from different phones are fine and worth keeping — the same
  scam template circulating widely is real signal.
- Ask people to forward what is already sitting in their inbox rather than
  waiting for new messages to arrive.
- `promo_marketing` and `otp_harvest` are the two subtypes most likely to
  be under-collected and most likely to break the model. Watch the counts.
