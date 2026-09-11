"""
Fine tune DistilBERT on the short-message dataset.

  source .venv/bin/activate
  python scripts/train_v2.py

Same architecture as v1 so the data is the only变 variable.
"""
import csv, os, random, time
import torch
from torch.utils.data import DataLoader, TensorDataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL = "distilbert-base-uncased"
OUTDIR = "models/distilbert_v2"
MAXLEN = 128
BATCH = 32
EPOCHS = 3
LR = 2e-5
SEED = 42
LABELS = {"legitimate": 0, "scam": 1}

random.seed(SEED); torch.manual_seed(SEED)
device = "mps" if torch.backends.mps.is_available() else "cpu"
print("device:", device)

def load(split):
    rows = list(csv.DictReader(open("data/processed/%s.csv" % split, newline="", encoding="utf-8")))
    return [r["text"] for r in rows], [LABELS[r["label"]] for r in rows]

tok = AutoTokenizer.from_pretrained(MODEL)

def encode(texts, labels):
    enc = tok(texts, truncation=True, padding="max_length", max_length=MAXLEN, return_tensors="pt")
    return TensorDataset(enc["input_ids"], enc["attention_mask"], torch.tensor(labels))

tr_x, tr_y = load("train")
va_x, va_y = load("val")
te_x, te_y = load("test")
print("train %d  val %d  test %d" % (len(tr_x), len(va_x), len(te_x)))

train_dl = DataLoader(encode(tr_x, tr_y), batch_size=BATCH, shuffle=True)
val_dl   = DataLoader(encode(va_x, va_y), batch_size=64)
test_dl  = DataLoader(encode(te_x, te_y), batch_size=64)

n_legit = tr_y.count(0); n_scam = tr_y.count(1); total = len(tr_y)
weights = torch.tensor([total/(2.0*n_legit), total/(2.0*n_scam)], dtype=torch.float).to(device)
print("class weights: legitimate %.3f scam %.3f" % (weights[0], weights[1]))

model = AutoModelForSequenceClassification.from_pretrained(MODEL, num_labels=2).to(device)
opt = torch.optim.AdamW(model.parameters(), lr=LR)
lossf = torch.nn.CrossEntropyLoss(weight=weights)

def evaluate(dl):
    model.eval()
    tp = fp = fn = tn = 0
    with torch.no_grad():
        for ids, mask, y in dl:
            ids, mask, y = ids.to(device), mask.to(device), y.to(device)
            pred = model(input_ids=ids, attention_mask=mask).logits.argmax(1)
            tp += int(((pred == 1) & (y == 1)).sum())
            fp += int(((pred == 1) & (y == 0)).sum())
            fn += int(((pred == 0) & (y == 1)).sum())
            tn += int(((pred == 0) & (y == 0)).sum())
    prec = tp / max(1, tp + fp)
    rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    acc = (tp + tn) / max(1, tp + tn + fp + fn)
    return acc, prec, rec, f1, (tp, fp, fn, tn)

best = -1
for ep in range(1, EPOCHS + 1):
    model.train()
    t0, run = time.time(), 0.0
    for i, (ids, mask, y) in enumerate(train_dl, 1):
        ids, mask, y = ids.to(device), mask.to(device), y.to(device)
        opt.zero_grad()
        loss = lossf(model(input_ids=ids, attention_mask=mask).logits, y)
        loss.backward(); opt.step()
        run += loss.item()
        if i % 50 == 0:
            print("  epoch %d  batch %d/%d  loss %.4f" % (ep, i, len(train_dl), run / i))
    acc, prec, rec, f1, _ = evaluate(val_dl)
    print("epoch %d done in %.0fs  val acc %.4f  prec %.4f  rec %.4f  F1 %.4f" % (
        ep, time.time() - t0, acc, prec, rec, f1))
    if f1 > best:
        best = f1
        os.makedirs(OUTDIR, exist_ok=True)
        model.save_pretrained(OUTDIR); tok.save_pretrained(OUTDIR)
        print("  saved (best so far)")

print("")
model = AutoModelForSequenceClassification.from_pretrained(OUTDIR).to(device)
acc, prec, rec, f1, (tp, fp, fn, tn) = evaluate(test_dl)
print("=" * 60)
print("HELD OUT TEST")
print("=" * 60)
print("accuracy %.4f  precision %.4f  recall %.4f  F1 %.4f" % (acc, prec, rec, f1))
print("true scam %d   false alarm %d   missed scam %d   true legit %d" % (tp, fp, fn, tn))
print("")
print("This number is NOT the Nigerian number. Run the Nigerian evaluation")
print("and the length experiment before believing anything.")
