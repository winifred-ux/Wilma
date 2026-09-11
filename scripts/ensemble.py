import csv, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

V1_REPO, V1_SUB = "winifred12/wilma-distilbert", "distilbert_v1"
V2_DIR = "models/distilbert_v2"
device = "mps" if torch.backends.mps.is_available() else "cpu"

def scam_index(model):
    lab = getattr(model.config, "id2label", None) or {}
    for i, name in lab.items():
        if str(name).strip().lower() in ("scam", "label_1", "1", "spam", "fraud"):
            if str(name).strip().lower() == "scam":
                return int(i)
    return 1

print("loading v1 from the Hub...")
t1 = AutoTokenizer.from_pretrained(V1_REPO, subfolder=V1_SUB)
m1 = AutoModelForSequenceClassification.from_pretrained(V1_REPO, subfolder=V1_SUB).to(device).eval()
print("v1 labels:", getattr(m1.config, "id2label", None))

t2 = AutoTokenizer.from_pretrained(V2_DIR)
m2 = AutoModelForSequenceClassification.from_pretrained(V2_DIR).to(device).eval()
print("v2 labels:", getattr(m2.config, "id2label", None))

s1, s2 = scam_index(m1), scam_index(m2)

rows = list(csv.DictReader(open("data/eval/nigerian_sms.csv", newline="", encoding="utf-8")))
texts = [r["text"] for r in rows]
y = torch.tensor([1 if r["label"].strip().lower() == "scam" else 0 for r in rows])

def scam_probs(tok, model, idx, maxlen):
    out = []
    for i in range(0, len(texts), 16):
        enc = tok(texts[i:i+16], truncation=True, padding=True, max_length=maxlen, return_tensors="pt").to(device)
        with torch.no_grad():
            out.append(torch.softmax(model(**enc).logits, dim=1)[:, idx].cpu())
    return torch.cat(out)

p1 = scam_probs(t1, m1, s1, 256)
p2 = scam_probs(t2, m2, s2, 128)

def score(pred, name):
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    print("%-26s acc %.3f  prec %.3f  rec %.3f  F1 %.3f  false %d  missed %d" % (
        name, (tp + tn) / len(y), prec, rec, f1, fp, fn))

print("")
print("=" * 78)
print("NIGERIAN SMS - 40 messages")
print("=" * 78)
score((p1 >= 0.5).long(), "v1 alone")
score((p2 >= 0.5).long(), "v2 alone")
print("")
score(((p1 >= 0.5) | (p2 >= 0.5)).long(), "OR (either flags)")
score(((p1 >= 0.5) & (p2 >= 0.5)).long(), "AND (both flag)")
print("")
for th in (0.4, 0.5, 0.6, 0.7, 0.8):
    score((((p1 + p2) / 2) >= th).long(), "mean prob >= %.1f" % th)
print("")
for th in (0.5, 0.7, 0.9, 0.95):
    score((torch.maximum(p1, p2) >= th).long(), "max prob >= %.2f" % th)

print("")
print("DISAGREEMENTS")
print("-" * 78)
for r, a, b in zip(rows, p1, p2):
    if (a >= 0.5) != (b >= 0.5):
        print("  v1 %.2f  v2 %.2f  truth %-10s %s" % (a, b, r["label"], r["text"][:70]))
