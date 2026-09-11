import csv, torch
from collections import defaultdict
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODELDIR = "models/distilbert_v2"
device = "mps" if torch.backends.mps.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(MODELDIR)
model = AutoModelForSequenceClassification.from_pretrained(MODELDIR).to(device).eval()
NAMES = ["legitimate", "scam"]

def predict(texts, bs=32):
    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i+bs], truncation=True, padding=True, max_length=128, return_tensors="pt").to(device)
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=1)
        for p in probs:
            j = int(p.argmax())
            out.append((NAMES[j], float(p[j])))
    return out

print("=" * 70)
print("NIGERIAN SMS EVALUATION")
print("=" * 70)
rows = list(csv.DictReader(open("data/eval/nigerian_sms.csv", newline="", encoding="utf-8")))
preds = predict([r["text"] for r in rows])
tp = fp = fn = tn = 0
mistakes = []
for r, (lab, conf) in zip(rows, preds):
    truth = r["label"].strip().lower()
    if lab == "scam" and truth == "scam":
        tp += 1
    elif lab == "scam":
        fp += 1
        mistakes.append(("FALSE ALARM", conf, r["text"]))
    elif truth == "scam":
        fn += 1
        mistakes.append(("MISSED SCAM", conf, r["text"]))
    else:
        tn += 1
prec = tp / max(1, tp + fp)
rec = tp / max(1, tp + fn)
f1 = 2 * prec * rec / max(1e-9, prec + rec)
acc = (tp + tn) / len(rows)
print("accuracy %.4f  precision %.4f  recall %.4f  F1 %.4f" % (acc, prec, rec, f1))
print("caught %d  false alarms %d  missed %d  correct legit %d" % (tp, fp, fn, tn))
print("")
print("BEFORE: accuracy 0.8000  precision 0.8333  recall 0.7500")
print("")
for kind, conf, text in mistakes:
    print("  %s (%.3f) %s" % (kind, conf, text[:95]))

print("")
print("=" * 70)
print("LENGTH EXPERIMENT")
print("=" * 70)
rows = list(csv.DictReader(open("data/eval/length_experiment.csv", newline="", encoding="utf-8")))
preds = predict([r["text"] for r in rows])
res = defaultdict(dict)
for r, (lab, conf) in zip(rows, preds):
    res[r["id"]][r["variant"]] = (lab, conf, len(r["text"]))
ORDER = ["short", "medium", "long"]
print("%-6s %-22s %-22s %-22s" % ("id", "short", "medium", "long"))
for rid in res:
    cells = []
    for v in ORDER:
        d = res[rid].get(v)
        cells.append("%s %.3f" % (d[0], d[1]) if d else "-")
    print("%-6s %-22s %-22s %-22s" % (rid, cells[0], cells[1], cells[2]))
print("")
for v in ORDER:
    ds = [res[r][v] for r in res if v in res[r]]
    hits = sum(1 for d in ds if d[0] == "scam")
    print("%-7s detected %d/%d (%3.0f%%)  mean conf %.3f  mean %d chars" % (
        v, hits, len(ds), 100.0 * hits / len(ds),
        sum(d[1] for d in ds) / len(ds), sum(d[2] for d in ds) / len(ds)))
print("")
print("BEFORE: short 0/8 (0%), medium 4/8 (50%), long 7/8 (88%)")
print("PASS CONDITION: detection flat across all three.")
