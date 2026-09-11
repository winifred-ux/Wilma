"""
Assemble the Wilma training set.

  python3 scripts/build_dataset.py

Sources: ExAIS (Nigerian legitimate) + Smishtank (short-form fraud).
The Nigerian evaluation set is NOT included anywhere - it stays the judge.

Near-duplicate templates are grouped and kept in the SAME split, so a
template never appears in both train and test. Without that, scores are
inflated by memorisation.
"""
import csv, os, random, re
from collections import Counter, defaultdict

SOURCES = ["data/collected/exais_clean.csv", "data/collected/smishtank.csv"]
OUTDIR = "data/processed"
HEADER = ["id","text","label","subtype","source","received","notes"]
SEED = 42
SPLITS = (0.80, 0.10, 0.10)

TOKEN = re.compile(r"<[A-Z_]+>")

def template_key(t):
    """Collapse a message to its template so variants group together."""
    t = t.lower()
    t = TOKEN.sub(" ", t)
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"[^a-z# ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:120]

rows, seen_exact = [], set()
for path in SOURCES:
    if not os.path.exists(path):
        print("missing %s" % path)
        raise SystemExit(1)
    for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
        k = r["text"].strip().lower()
        if not k or k in seen_exact:
            continue
        seen_exact.add(k)
        rows.append(r)

groups = defaultdict(list)
for r in rows:
    groups[template_key(r["text"])].append(r)

keys = sorted(groups)
random.Random(SEED).shuffle(keys)

n = len(rows)
want = [int(n * SPLITS[0]), int(n * (SPLITS[0] + SPLITS[1]))]
buckets, running = [[], [], []], 0
for k in keys:
    g = groups[k]
    i = 0 if running < want[0] else (1 if running < want[1] else 2)
    buckets[i].extend(g)
    running += len(g)

os.makedirs(OUTDIR, exist_ok=True)
names = ["train", "val", "test"]
for name, b in zip(names, buckets):
    with open(os.path.join(OUTDIR, name + ".csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in b:
            w.writerow({k: r.get(k, "") for k in HEADER})

print("=" * 68)
print("DATASET")
print("=" * 68)
print("unique messages: %d   template groups: %d" % (n, len(groups)))
big = sorted(((len(v), k) for k, v in groups.items()), reverse=True)[:5]
print("largest template groups:")
for c, k in big:
    print("  %4d  %s" % (c, k[:60]))
print("")
print("%-7s %7s %8s %8s %10s" % ("SPLIT", "rows", "scam", "legit", "med chars"))
for name, b in zip(names, buckets):
    lab = Counter(r["label"] for r in b)
    lens = sorted(len(r["text"]) for r in b)
    print("%-7s %7d %8d %8d %10d" % (
        name, len(b), lab["scam"], lab["legitimate"],
        lens[len(lens)//2] if lens else 0))

tr = Counter(r["label"] for r in buckets[0])
total = tr["scam"] + tr["legitimate"]
print("")
print("CLASS WEIGHTS for training (inverse frequency)")
for lab in ("legitimate", "scam"):
    print("  %-12s %.3f" % (lab, total / (2.0 * max(1, tr[lab]))))
print("")
print("SOURCE MIX (train)")
for k, v in Counter(r["source"] for r in buckets[0]).most_common():
    print("  %-12s %6d" % (k, v))
print("")
print("Written to %s/train.csv, val.csv, test.csv" % OUTDIR)
print("The Nigerian evaluation set is excluded and remains the real judge.")
