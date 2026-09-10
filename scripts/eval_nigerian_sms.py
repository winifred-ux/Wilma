"""
Evaluate the live Wilma API against a hand-built Nigerian SMS test set.

Uses only the Python standard library, so it needs no installs.

Run:
    export WILMA_API_KEY=your_key
    python3 scripts/eval_nigerian_sms.py
"""

import csv
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://winifred12-wilma.hf.space/classify"
CSV_PATH = "data/eval/nigerian_sms.csv"
API_KEY = os.environ.get("WILMA_API_KEY", "")
PAUSE_SECONDS = 0.3


def classify(text: str) -> dict:
    """Send one message to the API and return the parsed response."""
    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(API_URL, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    if API_KEY:
        request.add_header("Authorization", f"Bearer {API_KEY}")

    context = ssl.create_default_context()

    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                wait = 20 * (attempt + 1)
                print(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Gave up after repeated rate limiting")


def main() -> None:
    if not os.path.exists(CSV_PATH):
        sys.exit(f"Cannot find {CSV_PATH}. Run this from the project root.")

    with open(CSV_PATH, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    print(f"Evaluating {len(rows)} messages against {API_URL}")
    print(f"API key: {'yes' if API_KEY else 'no, running anonymous'}\n")

    # Confusion matrix counts, treating "scam" as the positive class.
    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0
    mistakes = []

    for index, row in enumerate(rows, start=1):
        text = row["text"]
        actual = row["label"].strip().lower()

        result = classify(text)
        predicted = result["verdict"].strip().lower()
        confidence = result["confidence"]

        if predicted == "scam" and actual == "scam":
            true_positive += 1
        elif predicted == "scam" and actual == "legitimate":
            false_positive += 1
            mistakes.append((text, actual, predicted, confidence))
        elif predicted == "legitimate" and actual == "legitimate":
            true_negative += 1
        else:
            false_negative += 1
            mistakes.append((text, actual, predicted, confidence))

        marker = "ok " if predicted == actual else "MISS"
        print(f"{index:>3}. {marker}  {predicted:<11} {confidence:.3f}  {text[:60]}")
        time.sleep(PAUSE_SECONDS)

    total = len(rows)
    accuracy = (true_positive + true_negative) / total if total else 0.0
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print("\n" + "=" * 62)
    print("RESULTS ON NIGERIAN SMS TEST SET")
    print("=" * 62)
    print(f"Messages       {total}")
    print(f"Accuracy       {accuracy:.2%}")
    print(f"Precision      {precision:.2%}   (of those flagged scam, how many were)")
    print(f"Recall         {recall:.2%}   (of real scams, how many were caught)")
    print(f"F1             {f1:.4f}")

    print("\nConfusion matrix")
    print("                    predicted scam   predicted legit")
    print(f"  actual scam       {true_positive:>14}   {false_negative:>15}")
    print(f"  actual legit      {false_positive:>14}   {true_negative:>15}")

    if mistakes:
        print(f"\n{len(mistakes)} MISTAKES")
        print("-" * 62)
        for text, actual, predicted, confidence in mistakes:
            print(f"  said {predicted} ({confidence:.3f}), was {actual}")
            print(f"    {text}\n")
    else:
        print("\nNo mistakes. Be suspicious of this, not pleased by it.")


if __name__ == "__main__":
    main()