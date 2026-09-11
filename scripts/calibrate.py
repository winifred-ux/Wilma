import csv, torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODELDIR = "models/distilbert_v2"
device = "mps" if torch.backends.mps.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(MODELDIR)
model = AutoModelForSequenceClassification.from_pretrained(MODELDIR).to(device).eval()

def logits_for(texts, bs=32):
    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i+bs], truncation=True, padding=True, max_length=128, return_tensors="pt").to(device)
        with torch.no_grad():
            out.append(model(**enc).logits.cpu())
    return torch.cat(out)

def load(path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    return [r["text"] for r in rows], torch.tensor(
        [1 if r["label"].strip().lower() == "scam" else 0 for r in rows])

vx, vy = load("data/processed/val.csv")
nx, ny = load("data/eval/nigerian_sms.csv")
vl, nl = logits_for(vx), logits_for(nx)

T = torch.ones(1, requires_grad=True)
opt = torch.optim.LBFGS([T], lr=0.01, max_iter=100)
nll = torch.nn.CrossEntropyLoss()
def step():
    opt.zero_grad()
    loss = nll(vl / T, vy)
    loss.backward()
    return loss
opt.step(step)
temp = float(T.detach())
print("fitted temperature: %.3f  (>1 means the model was overconfident)" % temp)

def ece(logits, y, t=1.0, bins=10):
    p = torch.softmax(logits / t, dim=1)
    conf, pred = p.max(1)
    correct = (pred == y).float()
    e = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        m = (conf > lo) & (conf <= hi)
        if m.sum() > 0:
            e += float(m.float().mean()) * abs(float(correct[m].mean()) - float(conf[m].mean()))
    return e

print("")
print("CALIBRATION ERROR (lower is better)")
print("  validation   raw %.4f   calibrated %.4f" % (ece(vl, vy), ece(vl, vy, temp)))
print("  Nigerian     raw %.4f   calibrated %.4f" % (ece(nl, ny), ece(nl, ny, temp)))

print("")
print("NIGERIAN SET: does any threshold help?  (diagnostic only, never tuned on)")
print("%-7s %7s %7s %7s %7s %7s" % ("thresh", "acc", "prec", "rec", "false", "missed"))
p = torch.softmax(nl / temp, dim=1)[:, 1]
for th in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]:
    pred = (p >= th).long()
    tp = int(((pred == 1) & (ny == 1)).sum()); fp = int(((pred == 1) & (ny == 0)).sum())
    fn = int(((pred == 0) & (ny == 1)).sum()); tn = int(((pred == 0) & (ny == 0)).sum())
    prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
    print("%-7.2f %7.3f %7.3f %7.3f %7d %7d" % (
        th, (tp + tn) / len(ny), prec, rec, fp, fn))
print("")
print("If accuracy never rises much above 0.625 at any threshold, the")
print("confidence score carries no usable signal on Nigerian SMS and only")
print("new training data can fix it.")
