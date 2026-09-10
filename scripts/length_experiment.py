import csv, json, os, time, urllib.request, urllib.error
from collections import defaultdict

API_URL = "https://winifred12-wilma.hf.space/classify"
CSV_PATH = "data/eval/length_experiment.csv"
API_KEY = os.environ.get("WILMA_API_KEY", "")

def classify(text):
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if API_KEY:
        req.add_header("Authorization", "Bearer " + API_KEY)
    wait = 5
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("   rate limited, waiting %ds..." % wait)
                time.sleep(wait)
                wait *= 2
                continue
            raise
    raise RuntimeError("gave up after rate limits")

rows = []
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        rows.append(row)

results = defaultdict(dict)
for i, row in enumerate(rows, 1):
    print("[%d/%d] %s / %s" % (i, len(rows), row["id"], row["variant"]))
    out = classify(row["text"])
    label = out.get("label") or out.get("prediction") or out.get("verdict")
    conf = out.get("confidence")
    if conf is None:
        scores = out.get("scores") or {}
        conf = max(scores.values()) if scores else 0.0
    results[row["id"]][row["variant"]] = {
        "label": str(label),
        "conf": float(conf),
        "chars": len(row["text"]),
    }
    time.sleep(1)

ORDER = ["short", "medium", "long"]

print("")
print("=" * 78)
print("SAME SCAM, THREE LENGTHS")
print("=" * 78)
print("%-10s %-26s %-26s %-26s" % ("id", "short", "medium", "long"))
for rid in results:
    cells = []
    for v in ORDER:
        d = results[rid].get(v)
        cells.append("%s %.3f (%dch)" % (d["label"], d["conf"], d["chars"]) if d else "-")
    print("%-10s %-26s %-26s %-26s" % (rid, cells[0], cells[1], cells[2]))

print("")
print("=" * 78)
print("DETECTION RATE BY LENGTH")
print("=" * 78)
for v in ORDER:
    ds = [results[r][v] for r in results if v in results[r]]
    if not ds:
        continue
    hits = sum(1 for d in ds if d["label"].lower() not in ("legitimate", "ham", "safe", "not_scam"))
    print("%-8s detected %d/%d (%.0f%%)   mean conf %.3f   mean length %d chars" % (
        v, hits, len(ds), 100.0 * hits / len(ds),
        sum(d["conf"] for d in ds) / len(ds),
        sum(d["chars"] for d in ds) / len(ds)))
