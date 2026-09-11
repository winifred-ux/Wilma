import csv, re, sys
from collections import Counter

csv.field_size_limit(10**7)
SRC = "data/collected/smishtank/dataset/final_dataset_output.csv"
OUT = "data/collected/smishtank.csv"
HEADER = ["id","text","label","subtype","source","received","notes"]

SUBTYPE = {
    "banking": "bank_phish",
    "delivery": "delivery_fee",
    "government": "other_scam",
    "telecom": "other_scam",
    "others": "other_scam",
    "wrong number": "impersonation",
    "hey mum/dad": "impersonation",
}
DROP_TYPES = {"spam", ""}

NORM = [
    (r"<PHONE_NUMBER>", "<PHONE>"),
    (r"<EMAIL_ADDRESS>", "<EMAIL>"),
    (r"<URL_ADDRESS>|<LINK>", "<URL>"),
    (r"<DATE_TIME>", "<DATE>"),
    (r"<US_DRIVER_LICENSE>|<US_BANK_NUMBER>|<US_SSN>|<US_PASSPORT>|<US_ITIN>|"
     r"<UK_NHS>|<MEDICAL_LICENSE>|<CREDIT_CARD>|<CRYPTO>|<IP_ADDRESS>|<EPIC>|"
     r"<MRP>|<ATTENTION>", "<ACCT>"),
    (r"<NAMED_ENTITY>|<NAME>|<LOCATION>|<NRP>|<ADV>", ""),
]

TOKEN = re.compile(r"<[A-Z_]+>")

def normalise(t):
    for pat, rep in NORM:
        t = re.sub(pat, rep, t)
    t = re.sub(r"(?:https?://|www\.)\S+", "<URL>", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()

rows = list(csv.DictReader(open(SRC, newline="", encoding="utf-8", errors="replace")))
mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"

kept, tokens, dropped = [], Counter(), Counter()
for r in rows:
    if (r.get("language") or "").strip() != "English":
        dropped["not english"] += 1
        continue
    st = (r.get("scam_type") or "").strip().lower()
    if st in DROP_TYPES:
        dropped["scam_type spam/blank"] += 1
        continue
    text = normalise(r.get("text") or "")
    if len(text) < 10:
        dropped["too short"] += 1
        continue
    for t in TOKEN.findall(text):
        tokens[t] += 1
    kept.append({"text": text, "subtype": SUBTYPE.get(st, "other_scam"), "scam_type": st})

lens = sorted(len(k["text"]) for k in kept)
print("kept %d" % len(kept))
for k, v in dropped.most_common():
    print("  dropped %-24s %6d" % (k, v))
print("")
print("PLACEHOLDER TOKENS FOUND")
for t, n in tokens.most_common(20):
    print("  %-22s %6d" % (t, n))
print("")
print("LENGTH median %d mean %d max %d over400 %d" % (
    lens[len(lens)//2], sum(lens)//len(lens), lens[-1],
    sum(1 for L in lens if L > 400)))
print("")
print("SUBTYPES")
for t, n in Counter(k["subtype"] for k in kept).most_common():
    print("  %-18s %6d" % (t, n))
print("")
for k in kept[:4]:
    print("  %s" % k["text"][:120])

if mode != "merge":
    print("")
    print("Inspection only. Nothing written.")
    sys.exit(0)

seen, out = set(), []
for k in kept:
    key = k["text"].lower()
    if key not in seen:
        seen.add(key)
        out.append(k)

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    for i, k in enumerate(out, 1):
        w.writerow(["s%05d" % i, k["text"], "scam", k["subtype"],
                    "smishtank", "", "smishtank:" + k["scam_type"]])
print("")
print("Wrote %d to %s (%d duplicates dropped)" % (len(out), OUT, len(kept) - len(out)))
