"""
ExAIS labels 'spam' as unsolicited bulk. Wilma needs 'scam' to mean fraud.
This splits the spam side into fraud, marketing, and needs-review.

  python3 scripts/triage_exais.py
"""
import csv, re
from collections import Counter

IN_PATH = "data/collected/exais.csv"
CLEAN_PATH = "data/collected/exais_clean.csv"
REVIEW_PATH = "data/collected/exais_review.csv"
HEADER = ["id", "text", "label", "subtype", "source", "received", "notes"]

# Checked FIRST. Real fraud - someone is trying to take money or credentials.
FRAUD = [
    ("promo_win", r"(congratulat|you have won|u have won|ur number.{0,20}won|winner|won the sum|lucky winner|claim your (prize|reward))"),
    ("419_inheritance", r"(barrister|next of kin|late (client|husband|father)|inheritance|solicitor|deceased|benefactor|will and testament)"),
    ("bank_phish", r"(bvn|your (atm|debit) card (has been|will be) (block|deactivat)|account (has been |will be )?(block|suspend|restrict|deactivat)|reactivate your account|verify your account|upgrade your account)"),
    ("otp_harvest", r"((send|forward|provide|share|reply with).{0,40}(otp|one time|pin|code|password)|card number|cvv)"),
    ("job_offer", r"(work from home|earn.{0,20}(daily|weekly)|no experience (is )?(needed|required)|urgent (recruitment|vacancy).{0,60}(whatsapp|apply))"),
    ("investment", r"(forex|bitcoin|crypto|double your (money|capital)|guaranteed (return|profit)|invest.{0,30}(profit|return|roi))"),
    ("loan_bait", r"(loan.{0,40}(no collateral|approved|processing fee)|instant (loan|cash))"),
    ("impersonation", r"(this is my new number|my phone (was|got) (stolen|damaged)|send.{0,20}(money|cash).{0,30}urgent)"),
    ("delivery_fee", r"(parcel|package|consignment).{0,60}(customs|clearance|fee|charge|held)"),
    ("other_scam", r"(western union|money gram|transfer the sum|compensation fund|donation|charity foundation|contact.{0,20}mr\.?\s|atm card.{0,30}deliver)"),
]

# Checked SECOND. Operator and subscription messaging - annoying, not fraud.
MARKETING = r"""(dial\s*\*|\*\d{3}\s*#|subscrib|unsubscrib|send\s+cancel|opt.?out|
validity period|data (plan|bundle)|night plan|browsing plan|caller\s?tun|
auto.?renew|renewed|glo|mtn|airtel|etisalat|9mobile|for more|free credit|
recharge (to|and) (get|enjoy)|bonus|top ?up|migrate to|enjoy \d)"""
MARKETING_RE = re.compile(MARKETING, re.I | re.X)

# Real bank transaction alerts. ExAIS mislabels some of these as spam.
BANK_ALERT = re.compile(
    r"(avail(able)? bal|prev bal|\bbal:|cracc|dracc|credit alert|debit alert|"
    r"acct\s*:|a/c\s*:|desc\s*:|txn id|ref\s*:\s*\d)", re.I)

# Telco service notices - bundles, expiry, menus. Not fraud.
TELCO = re.compile(
    r"(y'?ello|data (share|bundle)|\d+(\.\d+)?\s*(mb|gb)\b|expire|"
    r"plan (has )?expired|for (a )?list of options|send\s*:?\s*1 for|"
    r"day plans|week plans|monthly plans|welcome to )", re.I)

# User's own outgoing keyword replies - not messages at all.
JUNK = re.compile(r"^[A-Za-z]{2,12}$")

rows = list(csv.DictReader(open(IN_PATH, newline="", encoding="utf-8")))

clean, review = [], []
counts = Counter()

for r in rows:
    text, low = r["text"], r["text"].lower()

    if r["label"] == "legitimate":
        clean.append(r)
        counts["legitimate kept"] += 1
        continue

    if JUNK.match(text.strip()):
        counts["dropped junk"] += 1
        continue

    hit = None
    for name, pat in FRAUD:
        if re.search(pat, low, re.I):
            hit = name
            break

    if hit:
        r["subtype"] = hit
        r["notes"] = "auto: fraud"
        clean.append(r)
        counts["scam -> fraud"] += 1
    elif BANK_ALERT.search(text):
        r["label"] = "legitimate"
        r["subtype"] = "credit_alert" if re.search(r"credit|cracc", text, re.I) else "debit_alert"
        r["notes"] = "auto: relabelled bank alert"
        clean.append(r)
        counts["scam -> bank alert"] += 1
    elif MARKETING_RE.search(text) or TELCO.search(text):
        r["label"] = "legitimate"
        r["subtype"] = "promo_marketing"
        r["notes"] = "auto: relabelled marketing"
        clean.append(r)
        counts["scam -> marketing"] += 1
    else:
        r["notes"] = "REVIEW: fraud or marketing?"
        review.append(r)
        counts["needs review"] += 1

def write(path, rs):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rs:
            w.writerow({k: r.get(k, "") for k in HEADER})

write(CLEAN_PATH, clean)
write(REVIEW_PATH, review)

print("=" * 70)
print("TRIAGE")
print("=" * 70)
for k, v in counts.most_common():
    print("  %-22s %5d" % (k, v))

lab = Counter(r["label"] for r in clean)
print("")
print("%s: %d rows  (scam %d, legitimate %d)" % (
    CLEAN_PATH, len(clean), lab["scam"], lab["legitimate"]))
print("%s: %d rows for you to decide" % (REVIEW_PATH, len(review)))

sub = Counter(r["subtype"] for r in clean if r["label"] == "scam")
print("")
print("FRAUD SUBTYPES")
for s, n in sub.most_common():
    print("  %-18s %4d" % (s, n))

print("")
print("REVIEW SAMPLE")
print("-" * 70)
for r in review[:12]:
    print("  %s" % r["text"][:110])
