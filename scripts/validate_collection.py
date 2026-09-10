import csv, os, re, sys
from collections import Counter, defaultdict

CSV_PATH = os.environ.get("COLLECTION_CSV", "data/collected/messages.csv")

SCAM_SUBTYPES = {"promo_win","bank_phish","otp_harvest","419_inheritance",
                 "impersonation","investment","delivery_fee","job_offer",
                 "loan_bait","other_scam"}
LEGIT_SUBTYPES = {"otp","debit_alert","credit_alert","recharge",
                  "delivery_notice","appointment","promo_marketing",
                  "personal","other_legit"}
HEADER = ["id","text","label","subtype","source","received","notes"]

TARGET_TOTAL = 300
THIN = 8

LEAKS = [
    ("account number", re.compile(r"(?<!\d)\d{10}(?!\d)")),
    ("phone number", re.compile(r"(?:\+234|\b0)\d{9,10}\b")),
    ("url", re.compile(r"(?:https?://|www\.)\S+", re.I)),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
]

if not os.path.exists(CSV_PATH):
    print("No file at %s" % CSV_PATH)
    print("Copy the template to start:")
    print("  cp data/collected/messages_template.csv data/collected/messages.csv")
    sys.exit(1)

rows = []
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    if reader.fieldnames != HEADER:
        print("Header is wrong.")
        print("  expected: %s" % ",".join(HEADER))
        print("  found:    %s" % ",".join(reader.fieldnames or []))
        sys.exit(1)
    for n, row in enumerate(reader, 2):
        row["_line"] = n
        rows.append(row)

errors, warnings = [], []
seen_ids, seen_text = {}, defaultdict(list)

for r in rows:
    ln, rid = r["_line"], (r["id"] or "").strip()
    text = (r["text"] or "").strip()
    label = (r["label"] or "").strip()
    subtype = (r["subtype"] or "").strip()

    if not rid:
        errors.append("line %d: empty id" % ln)
    elif rid in seen_ids:
        errors.append("line %d: id %s already used on line %d" % (ln, rid, seen_ids[rid]))
    else:
        seen_ids[rid] = ln

    if not text:
        errors.append("line %d: empty text" % ln)
    else:
        seen_text[text.lower()].append(rid)

    if label not in ("scam", "legitimate"):
        errors.append("line %d: label must be scam or legitimate, got '%s'" % (ln, label))
    elif label == "scam" and subtype not in SCAM_SUBTYPES:
        errors.append("line %d: '%s' is not a scam subtype" % (ln, subtype))
    elif label == "legitimate" and subtype not in LEGIT_SUBTYPES:
        errors.append("line %d: '%s' is not a legitimate subtype" % (ln, subtype))

    for name, pat in LEAKS:
        if pat.search(text):
            warnings.append("line %d (%s): possible unredacted %s" % (ln, rid, name))

print("=" * 70)
print("WILMA COLLECTION CHECK   %s" % CSV_PATH)
print("=" * 70)
print("rows: %d" % len(rows))

if errors:
    print("")
    print("ERRORS (%d) - fix these" % len(errors))
    for e in errors[:40]:
        print("  " + e)
    if len(errors) > 40:
        print("  ... and %d more" % (len(errors) - 40))

dupes = {t: ids for t, ids in seen_text.items() if len(ids) > 1}
if dupes:
    print("")
    print("DUPLICATE TEXT (%d) - fine if from different phones" % len(dupes))
    for t, ids in list(dupes.items())[:10]:
        print("  %s  ->  %s" % (", ".join(ids), t[:55]))

if warnings:
    print("")
    print("REDACTION WARNINGS (%d) - check these by eye" % len(warnings))
    for w in warnings[:25]:
        print("  " + w)
    if len(warnings) > 25:
        print("  ... and %d more" % (len(warnings) - 25))

valid = [r for r in rows if r["label"] in ("scam", "legitimate")]
labels = Counter(r["label"] for r in valid)
scam_n, legit_n = labels.get("scam", 0), labels.get("legitimate", 0)

print("")
print("BALANCE")
print("  scam        %d" % scam_n)
print("  legitimate  %d" % legit_n)
if scam_n and legit_n:
    ratio = max(scam_n, legit_n) / min(scam_n, legit_n)
    if ratio > 1.5:
        print("  -> skewed %.1f:1. Collect more %s." % (
            ratio, "legitimate" if legit_n < scam_n else "scam"))

for label, allowed in (("scam", SCAM_SUBTYPES), ("legitimate", LEGIT_SUBTYPES)):
    counts = Counter(r["subtype"] for r in valid if r["label"] == label)
    print("")
    print("%s SUBTYPES" % label.upper())
    for s in sorted(allowed):
        n = counts.get(s, 0)
        flag = "   <- thin" if n < THIN else ""
        print("  %-18s %3d%s" % (s, n, flag))

lengths = sorted(len(r["text"]) for r in valid if r["text"])
if lengths:
    long_n = sum(1 for L in lengths if L > 400)
    print("")
    print("LENGTH")
    print("  median %d chars   mean %d chars   max %d chars" % (
        lengths[len(lengths)//2], sum(lengths)//len(lengths), lengths[-1]))
    print("  over 400 chars: %d (%.0f%%)" % (long_n, 100.0*long_n/len(lengths)))
    if long_n > len(lengths) * 0.25:
        print("  -> too many long messages. Short SMS is the point.")

sources = Counter((r["source"] or "unknown").strip() for r in valid)
print("")
print("SOURCES")
for s, n in sources.most_common():
    print("  %-14s %d" % (s, n))

print("")
print("=" * 70)
if errors:
    print("NOT READY - %d errors to fix first" % len(errors))
elif len(valid) < 200:
    print("NOT READY - %d messages. Need 200 minimum, %d is the target." % (
        len(valid), TARGET_TOTAL))
elif len(valid) < TARGET_TOTAL:
    print("USABLE - %d messages. Fine tuning can start. %d more hits target." % (
        len(valid), TARGET_TOTAL - len(valid)))
else:
    print("READY - %d messages, no errors. Good to fine tune." % len(valid))
print("=" * 70)
