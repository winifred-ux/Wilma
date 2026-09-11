"""
Load the ExAIS Nigerian SMS corpus into Wilma's collection schema.
Files have NO header row. Layout is:
  0 SMS | 1 direction | 2 sender | 3 sender | 4 datetime | 5 length | 6 label | 7+ text

  python3 scripts/load_exais.py inspect
  python3 scripts/load_exais.py merge
"""
import csv, os, re, sys, zipfile
from collections import Counter

SRC_DIR = "data/collected/exais"
OUT_PATH = "data/collected/exais.csv"
HEADER = ["id", "text", "label", "subtype", "source", "received", "notes"]

REDACT = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<EMAIL>"),
    (re.compile(r"(?:https?://|www\.)\S+", re.I), "<URL>"),
    (re.compile(r"(?:\+234|\b0)\d{9,10}\b"), "<PHONE>"),
    (re.compile(r"(?<!\d)\d{10,}(?!\d)"), "<ACCT>"),
]
CODE_NEAR = re.compile(r"\b(otp|code|pin|token)\b[^0-9]{0,20}(\d{4,8})\b", re.I)

SUBTYPE_RULES_SCAM = [
    ("otp_harvest", r"\b(send|forward|provide|share).{0,30}\b(otp|code|pin)\b"),
    ("promo_win", r"\b(congratulation|you have won|u have won|winner|prize|lucky)\b"),
    ("bank_phish", r"\b(bvn|account.{0,20}(block|restrict|suspend)|verify your account)\b"),
    ("419_inheritance", r"\b(barrister|next of kin|late client|inheritance|solicitor)\b"),
    ("investment", r"\b(forex|crypto|bitcoin|invest|guaranteed return|double your)\b"),
    ("job_offer", r"\b(work from home|earn.{0,15}daily|recruitment|no experience)\b"),
    ("delivery_fee", r"\b(parcel|package|customs|clearance|courier)\b"),
    ("loan_bait", r"\b(loan|no collateral|instant cash)\b"),
    ("impersonation", r"\b(new number|my phone (broke|fell|got stolen))\b"),
]
SUBTYPE_RULES_LEGIT = [
    ("otp", r"\b(otp|one[- ]time|verification code|do not share)\b"),
    ("debit_alert", r"\b(debit|withdraw|\bdt:|pos\b|acct)"),
    ("credit_alert", r"\b(credit|deposit|lodgment)\b"),
    ("recharge", r"\b(recharge|airtime|top ?up|data (bundle|plan)|txn id)\b"),
    ("delivery_notice", r"\b(dispatch|out for delivery|your order|tracking)\b"),
    ("appointment", r"\b(appointment|reminder|scheduled|lecture|exam|venue|invite)\b"),
    ("promo_marketing", r"\b(offer|promo|discount|dial \*|subscribe|free credit|enjoy)\b"),
]

LABEL_AT = 6
TEXT_AT = 7
DATE_AT = 4

def unzip_all():
    for root, _, names in os.walk(SRC_DIR):
        for n in names:
            if n.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(os.path.join(root, n)) as z:
                        z.extractall(root)
                except Exception as e:
                    print("  could not unzip %s: %s" % (n, e))

def find_csvs():
    files = []
    for root, _, names in os.walk(SRC_DIR):
        for n in names:
            if n.lower().endswith((".csv", ".txt", ".tsv")):
                files.append(os.path.join(root, n))
    return sorted(files)

def read_rows(path):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.reader(f))
        except UnicodeDecodeError:
            continue
    return []

def find_label(cells):
    """Label is normally index 6, but scan nearby in case a file is shifted."""
    for i in (LABEL_AT, 5, 7, 4, 8):
        if i < len(cells):
            v = cells[i].strip().upper().rstrip(".")
            if v in ("HAM", "SPAM"):
                return i, ("legitimate" if v == "HAM" else "scam")
    return None, None

def redact(t):
    t = CODE_NEAR.sub(lambda m: m.group(1) + " <CODE>", t)
    for pat, rep in REDACT:
        t = pat.sub(rep, t)
    return re.sub(r"\s+", " ", t).strip()

def norm_date(v):
    v = (v or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", v)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return ""

def subtype_for(label, text):
    rules = SUBTYPE_RULES_SCAM if label == "scam" else SUBTYPE_RULES_LEGIT
    low = text.lower()
    for name, pat in rules:
        if re.search(pat, low):
            return name
    return "other_scam" if label == "scam" else "other_legit"

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if not os.path.isdir(SRC_DIR):
        print("No folder at %s" % SRC_DIR)
        sys.exit(1)

    unzip_all()
    files = find_csvs()
    print("Found %d data files" % len(files))

    out, no_label, too_short = [], 0, 0
    report = []

    for path in files:
        rows = read_rows(path)
        kept = 0
        for cells in rows:
            if len(cells) <= TEXT_AT:
                no_label += 1
                continue
            li, label = find_label(cells)
            if label is None:
                no_label += 1
                continue
            # text may have been split on unquoted commas - rejoin everything after the label
            parts = [c if c is not None else "" for c in cells[li + 1:]]
            while parts and not parts[-1].strip():
                parts.pop()
            text = redact(",".join(parts).strip())
            if len(text) < 5:
                too_short += 1
                continue
            out.append({
                "text": text,
                "label": label,
                "received": norm_date(cells[DATE_AT] if len(cells) > DATE_AT else ""),
            })
            kept += 1
        report.append((os.path.relpath(path, SRC_DIR), len(rows), kept))

    print("")
    print("=" * 70)
    print("%-40s %8s %8s" % ("FILE", "ROWS", "KEPT"))
    print("=" * 70)
    for name, total, kept in report:
        flag = "" if kept else "   <- nothing parsed"
        print("%-40s %8d %8d%s" % (name[:40], total, kept, flag))

    labels = Counter(o["label"] for o in out)
    lens = sorted(len(o["text"]) for o in out)
    print("")
    print("USABLE: %d   scam %d   legitimate %d" % (
        len(out), labels["scam"], labels["legitimate"]))
    print("dropped: %d unreadable label, %d too short" % (no_label, too_short))
    if lens:
        print("length: median %d, mean %d, max %d, over 400 chars %d (%.0f%%)" % (
            lens[len(lens)//2], sum(lens)//len(lens), lens[-1],
            sum(1 for L in lens if L > 400),
            100.0*sum(1 for L in lens if L > 400)/len(lens)))

    print("")
    print("SAMPLE - read these, they must look like real messages")
    print("-" * 70)
    for o in out[:3] + out[len(out)//2:len(out)//2+3] + out[-3:]:
        print("[%s] %s" % (o["label"][:4], o["text"][:150]))

    if mode != "merge":
        print("")
        print("Inspection only. Nothing written.")
        return

    seen, deduped = set(), []
    for o in out:
        k = o["text"].lower()
        if k not in seen:
            seen.add(k)
            deduped.append(o)

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for i, o in enumerate(deduped, 1):
            w.writerow(["e%05d" % i, o["text"], o["label"],
                        subtype_for(o["label"], o["text"]),
                        "exais", o["received"], "auto-subtyped"])

    print("")
    print("Wrote %d to %s (%d duplicates dropped)" % (
        len(deduped), OUT_PATH, len(out) - len(deduped)))

main()
