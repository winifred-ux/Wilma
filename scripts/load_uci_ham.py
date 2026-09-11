import csv, re, sys
from collections import Counter

SRC = "data/collected/uci/SMSSpamCollection"
OUT = "data/collected/uci_ham.csv"
HEADER = ["id","text","label","subtype","source","received","notes"]

DATE = re.compile(
    r"\b\d{1,2}[/-](?:\d{1,2}|[A-Za-z]{3})[/-]\d{2,4}\b(?:\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)?"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?\b")
SUBS = [
    (r"(?:https?://|www\.)\S+", "<URL>"),
    (r"[\w.+-]+@[\w-]+\.[\w.]+", "<EMAIL>"),
    (r"(?:\+\d{1,3}\s?)?\b0?\d{9,11}\b", "<PHONE>"),
    (r"(?<!\d)\d{10,}(?!\d)", "<ACCT>"),
]
RULES = [
    ("otp", r"\b(otp|verification code|passcode|your code is)\b"),
    ("appointment", r"\b(appointment|meeting|reminder|class|lecture|interview)\b"),
    ("promo_marketing", r"\b(offer|discount|sale|free delivery|voucher)\b"),
]

def norm(t):
    t = DATE.sub("<DATE>", t)
    for pat, rep in SUBS:
        t = re.sub(pat, rep, t)
    return re.sub(r"\s+", " ", t).strip()

def subtype(t):
    for name, pat in RULES:
        if re.search(pat, t, re.I):
            return name
    return "personal"

rows = []
with open(SRC, encoding="utf-8", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\n").split("\t", 1)
        if len(parts) != 2 or parts[0].strip().lower() != "ham":
            continue
        t = norm(parts[1])
        if len(t) >= 10:
            rows.append(t)

seen, out = set(), []
for t in rows:
    if t.lower() not in seen:
        seen.add(t.lower())
        out.append(t)

mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
lens = sorted(len(t) for t in out)
print("ham rows: %d (%d duplicates dropped)" % (len(out), len(rows) - len(out)))
print("length median %d mean %d max %d over400 %d" % (
    lens[len(lens)//2], sum(lens)//len(lens), lens[-1], sum(1 for L in lens if L > 400)))
print("")
print("TOKENS")
for tok in ("<URL>","<EMAIL>","<PHONE>","<ACCT>","<DATE>"):
    print("  %-8s %5d" % (tok, sum(1 for t in out if tok in t)))
print("")
print("SUBTYPES")
for k, v in Counter(subtype(t) for t in out).most_common():
    print("  %-18s %5d" % (k, v))
print("")
for t in out[:4]:
    print("  %s" % t[:110])

if mode != "merge":
    print("")
    print("Inspection only. Nothing written.")
    sys.exit(0)

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    for i, t in enumerate(out, 1):
        w.writerow(["u%05d" % i, t, "legitimate", subtype(t), "uci", "", "uci ham"])
print("")
print("Wrote %d to %s" % (len(out), OUT))
