"""
Wilma -- FastAPI service.

Wraps the trained DistilBERT binary and multi-class models behind a
clean REST interface. Single-message classify, batch classify, and
health endpoints. Models are loaded once at startup and held in
memory.

Run locally:
    uvicorn wilma.api.service:app --host 0.0.0.0 --port 8000 --reload

Then visit:
    http://localhost:8000/docs    -- interactive Swagger UI
    http://localhost:8000/health  -- health check
"""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BINARY_MODEL_PATH = PROJECT_ROOT / "models" / "distilbert_v1"
MULTICLASS_MODEL_PATH = PROJECT_ROOT / "models" / "distilbert_v1_multiclass"

MAX_LENGTH = 256
BATCH_LIMIT = 50

# Wilma version for API responses
WILMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=20_000,
        description="Message text to classify",
        examples=["URGENT BUSINESS ASSISTANCE: I need your help to transfer 25 million dollars"],
    )
    multiclass: bool = Field(
        default=False,
        description="If true, return fine-grained category. Otherwise return scam/legitimate only.",
    )


class BatchClassifyRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=BATCH_LIMIT)
    multiclass: bool = Field(default=False)


class TokenSignal(BaseModel):
    token: str
    score: float


class ClassifyResponse(BaseModel):
    verdict: str = Field(..., description="Predicted class label")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Probability of predicted class")
    is_scam: bool = Field(..., description="True if predicted class is anything other than legitimate")
    model: str = Field(..., description="Model identifier")
    latency_ms: float
    probabilities: dict[str, float] = Field(..., description="Per-class probabilities")


class BatchClassifyResponse(BaseModel):
    results: list[ClassifyResponse]
    total_latency_ms: float
    count: int


class HealthResponse(BaseModel):
    status: str
    version: str
    models_loaded: bool
    device: str


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

class ModelBundle:
    def __init__(self, path: Path, device: torch.device):
        self.path = path
        self.tokenizer = AutoTokenizer.from_pretrained(str(path))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(path)).to(device).eval()
        self.id2label = self.model.config.id2label
        self.device = device


_state: dict[str, Optional[object]] = {
    "binary": None,
    "multiclass": None,
    "device": None,
}


def _select_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load both models once at startup; drop them at shutdown."""
    device = _select_device()
    _state["device"] = device

    print(f"[wilma-api] Loading binary model from {BINARY_MODEL_PATH}")
    _state["binary"] = ModelBundle(BINARY_MODEL_PATH, device)

    print(f"[wilma-api] Loading multi-class model from {MULTICLASS_MODEL_PATH}")
    _state["multiclass"] = ModelBundle(MULTICLASS_MODEL_PATH, device)

    print(f"[wilma-api] Ready. Device: {device}")
    yield
    print("[wilma-api] Shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Wilma API",
    description="AI-powered scam and fraud detection for SMS, email, and chat messages.",
    version=WILMA_VERSION,
    lifespan=lifespan,
)

# Open CORS for landing-page demo. In production, restrict to your domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Inference helpers
# ---------------------------------------------------------------------------

def _classify_single(text: str, bundle: ModelBundle) -> ClassifyResponse:
    started = time.perf_counter()
    enc = bundle.tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
        padding=False,
    ).to(bundle.device)

    with torch.no_grad():
        logits = bundle.model(**enc).logits

    probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().tolist()
    cls_id = int(max(range(len(probs)), key=lambda i: probs[i]))
    verdict = bundle.id2label[cls_id]
    confidence = float(probs[cls_id])
    probabilities = {bundle.id2label[i]: float(p) for i, p in enumerate(probs)}

    latency_ms = (time.perf_counter() - started) * 1000.0
    model_name = "DistilBERT v1 binary" if len(bundle.id2label) == 2 else "DistilBERT v1 multi-class"

    return ClassifyResponse(
        verdict=verdict,
        confidence=confidence,
        is_scam=(verdict != "legitimate"),
        model=model_name,
        latency_ms=round(latency_ms, 2),
        probabilities=probabilities,
    )


def _bundle_for(multiclass: bool) -> ModelBundle:
    bundle = _state["multiclass" if multiclass else "binary"]
    if bundle is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet")
    return bundle  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "Wilma API",
        "version": WILMA_VERSION,
        "description": "Scam and fraud detection for SMS, email, and chat messages.",
        "docs": "/docs",
        "endpoints": ["/classify", "/classify/batch", "/health"],
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    device = _state["device"]
    return HealthResponse(
        status="ok",
        version=WILMA_VERSION,
        models_loaded=(_state["binary"] is not None and _state["multiclass"] is not None),
        device=str(device) if device else "unknown",
    )


@app.post("/classify", response_model=ClassifyResponse, tags=["inference"])
def classify(req: ClassifyRequest) -> ClassifyResponse:
    bundle = _bundle_for(req.multiclass)
    return _classify_single(req.text, bundle)


@app.post("/classify/batch", response_model=BatchClassifyResponse, tags=["inference"])
def classify_batch(req: BatchClassifyRequest) -> BatchClassifyResponse:
    bundle = _bundle_for(req.multiclass)
    started = time.perf_counter()
    results = [_classify_single(text, bundle) for text in req.texts]
    total = (time.perf_counter() - started) * 1000.0
    return BatchClassifyResponse(
        results=results,
        total_latency_ms=round(total, 2),
        count=len(results),
    )
