---
title: Wilma
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: AI fraud detection.
---

# Wilma: AI fraud detection for Nigerian messages

Wilma is an API that checks SMS, email and chat messages and decides if they
are scams. It is built for Nigerian fraud patterns such as BVN and NIN blocking
threats, fake prize draws, fake debit alerts and 419 inheritance messages.

**Live:** [winifred12-wilma.hf.space](https://winifred12-wilma.hf.space)
&nbsp;|&nbsp; **API docs:** [/docs](https://winifred12-wilma.hf.space/docs)

Built and maintained by Winifred Ajah.

## Key results

| What | Result |
|---|---|
| Training data | 17,131 unique messages from two public SMS corpora, split by template group so near duplicates never cross between train and test |
| Length bias found and fixed | The first model was judging message length, not fraud. Short scams (60 chars): **0 of 8** caught before, **6 of 8** after fine tuning on short messages |
| Two models together | On a 40 message Nigerian evaluation set, the two models together flagged **20 of 20 scams** |
| Three state verdict | `block` when both models agree, `review` when only one flags, `pass` when neither does |

Full numbers, including every failure, are in [docs/EVALUATION.md](docs/EVALUATION.md).

## How the verdict works

The two fine tuned DistilBERT models fail on different messages:

- **v1** was trained on long form email corpora. It knows 419 and prize language.
- **v2** was fine tuned on short SMS smishing. It knows credential harvesting texts.

So instead of trusting one score, `/verdict` combines them the way a bank
fraud team works: auto block the certain cases, send the uncertain ones to a
human, and let the rest through.

| Models flag it | Verdict | On the Nigerian set |
|---|---|---|
| both | `block` | precision 0.778, 2 false alarms in 40 |
| only one | `review` | recall 1.000, no scam got past |
| neither | `pass` | |

If the second model fails to load, the endpoint returns `review` instead of
`block`, because auto blocking on one opinion is the most costly mistake.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/verdict` | Three state verdict from both models |
| POST | `/classify` | Single model classification (v1) |
| POST | `/classify/batch` | Up to 50 messages at once |
| GET | `/usage` | Message usage per API key, for billing |
| GET | `/health` | Health check |
| GET | `/docs` | Interactive Swagger UI |

### Example

```bash
curl -X POST https://winifred12-wilma.hf.space/classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Your BVN has been blocked. Click this link to reactivate."}'
```

## How it is built

- **Backend:** FastAPI, running in Docker on Hugging Face Spaces
- **Models:** two fine tuned DistilBERT models, loaded once at startup
- **Auth:** Supabase, with API keys stored as hashes, never as plain text
- **Rate limiting:** per API key and per IP
- **Usage metering:** every classified message is logged per key for billing
- **Explainability:** token level attributions with Integrated Gradients, showing which words pushed a message towards a scam verdict
- **Front end:** hand built HTML and CSS, no framework

## Known limitations

I document where Wilma fails, not just where it works.

- **A real OTP message was auto blocked.** Both models agreed at over 0.99. The
  models still confuse genuine bank and transaction messages with scams.
  Collecting real legitimate Nigerian SMS is the top priority.
- **The Nigerian evaluation set is only 40 messages.** The error bars are wide.
- **Confidence scores are not calibrated,** so they should not be read as probabilities.
- **`/verdict` takes about 1.6 seconds** on free CPU hardware, since it runs two models.
- **Rate limit state lives in memory,** so it resets when the Space restarts.
- **English only.** Not yet tested on Pidgin or code switched messages.

## Documentation

- [docs/EVALUATION.md](docs/EVALUATION.md): every experiment, metric and failure
- [docs/DATASET.md](docs/DATASET.md): data sources, splits and leakage controls
- [docs/COLLECTION.md](docs/COLLECTION.md): how new Nigerian SMS data is collected and labelled

## Data sources

- **Smishtank (Smishing-Dataset-IMC25):** real user reported SMS phishing, CC BY 4.0.
- **ExAIS SMS Spam Dataset** (FUNAAB, Nigeria): used for legitimate messages only.

See [docs/DATASET.md](docs/DATASET.md) for full attribution.

## Earlier version

The earlier SaaS front end (landing page, sign up, dashboard, API key
generation pages) is kept on the
[`saas-version`](https://github.com/winifred-ux/Wilma/tree/saas-version) branch.
