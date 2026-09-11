"""
Review the ExAIS spam leftovers, most fraud-like first.

  python3 scripts/review_exais.py          # review
  python3 scripts/review_exais.py apply    # fold decisions into exais_clean.csv
"""
import csv, os, re, sys
from collections import Counter

REVIEW = "data/collected/exais_review.csv"
CLEAN = "data/collected/exais_clean.csv"
DECISIONS = "data/collected/review_decisions.csv"
HEADER = ["id", "text", "label", "subtype", "source", "received", "notes"]

# Signals that a message is trying to get money or credentials from a person.
SIGNALS = [
    (5, r"(congratulat|you have won|winner|prize|reward|selected)"),
    (5, r"(barrister|next of kin|late (client|husband)|inheritance|deceased|benefactor)"),
    (5, r"(bvn|atm card|card number|cvv|your pin|account number)"),
    (4, r"(send|forward|reply with|provide).{0,30}(otp|code|pin|password|details)"),
    (4, r"(western union|money ?gram|transfer the sum|compensation|foundation|donation)"),
    (4, r"(work from home|earn.{0,20}(daily|weekly)|no experience|vacancy|recruitment)"),
    (4, r"(forex|bitcoin|crypto|investment|double your|guaranteed (profit|return))"),
    (3, r"(urgent|immediately|within \d+ (hours?|minutes?)|expires? (today|soon)|act now)"),
    (3, r"(loan|collateral|instant cash|credit facility)"),
    (3, r"(call|contact|whatsapp|chat).{0,25}(me|us|now|on)\b"),
    (3, r"(dear (customer|sir|madam|friend|beloved)|attention:)"),
    (2, r"(n\s?\d{3,}|ngn\s?\d{3,}|\d+\s?(million|thousand)|\$\s?\d)"),
    (2, r"<PHONE>|<EMAIL>"),
    (2, r"(god|blessed|almighty|pray)"),
    (2, r"(claim|collect|release|process).{0,20}(fund|payment|money|prize)"),
    (-3, r"(dial\s*\*|\*\d{3}#|subscrib|data (plan|bundle)|airtime|\bmb\b|\bgb\b)"),
    (-3, r"(y'?ello|glo|mtn|airtel|etisalat|9mobile)"),
]
SIGNALS = [(w, re.compile(p, re.I)) for w, p in SIGNALS]

def score(text):
    return sum(w for w, p in SIGNALS if p.search(text))

def load_decisions():
    d = {}
    if os.path.exists(DECISIONS):
        for r in csv.DictReader(open(DECISIONS, newline="", encoding="utf-8")):
            d[r["id"]] = r["decision"]
    return d

def save_decisions(d):
    with open(DECISIONS, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "decision"])
        for k, v in d.items():
            w.writerow([k, v])

rows = list(csv.DictReader(open(REVIEW, newline="", encoding="utf-8")))
for r in rows:
    r["_score"] = score(r["text"])
rows.sort(key=lambda r: -r["_score"])

decisions = load_decisions()

if len(sys.argv) > 1 and sys.argv[1] == "apply":
    clean = list(csv.DictReader(open(CLEAN, newline="", encoding="utf-8")))
    added = Counter()
    for r in rows:
        d = decisions.get(r["id"])
        if d == "f":
            r["label"], r["subtype"], r["notes"] = "scam", "other_scam", "reviewed: fraud"
        elif d == "m":
            r["label"], r["subtype"], r["notes"] = "legitimate", "promo_marketing", "reviewed: marketing"
        elif d == "l":
            r["label"], r["subtype"], r["notes"] = "legitimate", "other_legit", "reviewed: legitimate"
        else:
            continue
        clean.append({k: r.get(k, "") for k in HEADER})
        added[d] += 1
    with open(CLEAN, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in clean:
            w.writerow({k: r.get(k, "") for k in HEADER})
    lab = Counter(r["label"] for r in clean)
    print("Added %d fraud, %d marketing, %d legitimate" % (
        added["f"], added["m"], added["l"]))
    print("%s now %d rows (scam %d, legitimate %d)" % (
        CLEAN, len(clean), lab["scam"], lab["legitimate"]))
    sys.exit(0)

todo = [r for r in rows if r["id"] not in decisions]
print("=" * 72)
print("REVIEW  -  %d left of %d, highest fraud score first" % (len(todo), len(rows)))
print("  f = fraud    m = telco/marketing    l = legitimate other")
print("  s = skip     q = save and quit")
print("=" * 72)

try:
    for i, r in enumerate(todo, 1):
        print("")
        print("[%d/%d]  score %d" % (i, len(todo), r["_score"]))
        print("-" * 72)
        print(r["text"][:600])
        print("-" * 72)
        while True:
            ans = input("f/m/l/s/q > ").strip().lower()
            if ans in ("f", "m", "l", "s", "q"):
                break
        if ans == "q":
            break
        if ans != "s":
            decisions[r["id"]] = ans
except (KeyboardInterrupt, EOFError):
    print("")

save_decisions(decisions)
c = Counter(decisions.values())
print("")
print("Saved %d decisions: %d fraud, %d marketing, %d legitimate" % (
    len(decisions), c["f"], c["m"], c["l"]))
print("When you are done, run:  python3 scripts/review_exais.py apply")
