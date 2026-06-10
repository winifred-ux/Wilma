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
import httpx


import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# Load models from Hugging Face Hub instead of local disk so the deploy
# image stays small. The Hub repo "winifred12/wilma-distilbert" contains
# both fine-tuned models in subfolders.
HF_REPO = "winifred12/wilma-distilbert"
BINARY_MODEL_PATH = HF_REPO            # subfolder specified at load time
MULTICLASS_MODEL_PATH = HF_REPO        # subfolder specified at load time
BINARY_SUBFOLDER = "distilbert_v1"
MULTICLASS_SUBFOLDER = "distilbert_v1_multiclass"

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
    def __init__(self, repo_or_path, device: torch.device, subfolder: str = ""):
        self.repo_or_path = repo_or_path
        self.subfolder = subfolder
        kwargs = {"subfolder": subfolder} if subfolder else {}
        self.tokenizer = AutoTokenizer.from_pretrained(str(repo_or_path), **kwargs)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(repo_or_path), **kwargs
        ).to(device).eval()
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

    print(f"[wilma-api] Loading binary model from {BINARY_MODEL_PATH}/{BINARY_SUBFOLDER}")
    _state["binary"] = ModelBundle(BINARY_MODEL_PATH, device, subfolder=BINARY_SUBFOLDER)

    print(f"[wilma-api] Loading multi-class model from {MULTICLASS_MODEL_PATH}/{MULTICLASS_SUBFOLDER}")
    _state["multiclass"] = ModelBundle(MULTICLASS_MODEL_PATH, device, subfolder=MULTICLASS_SUBFOLDER)

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


# --- API key validation ---
SUPABASE_URL_FOR_AUTH = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY_FOR_AUTH = os.environ.get("SUPABASE_SERVICE_KEY", "")


async def verify_api_key_optional(authorization: Optional[str] = Header(default=None)):
    """
    Optional API key validation.
    - No Authorization header: anonymous access allowed (for landing page demo)
    - Bearer token present: must be a valid, non-revoked Wilma API key
    """
    if not authorization:
        return None  # Anonymous access allowed

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header. Use 'Bearer YOUR_API_KEY'."
        )

    key = authorization[7:].strip()

    if not key.startswith("wlm_"):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key format. Wilma keys start with 'wlm_'."
        )

    if not SUPABASE_URL_FOR_AUTH or not SUPABASE_SERVICE_KEY_FOR_AUTH:
        raise HTTPException(
            status_code=500,
            detail="Server is not configured for API key validation."
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SUPABASE_URL_FOR_AUTH}/rest/v1/api_keys",
                params={
                    "key_full": f"eq.{key}",
                    "revoked_at": "is.null",
                    "select": "id,user_id,name",
                    "limit": "1",
                },
                headers={
                    "apikey": SUPABASE_SERVICE_KEY_FOR_AUTH,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY_FOR_AUTH}",
                },
            )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Could not validate API key (auth service unreachable)."
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Could not validate API key.")

    keys = response.json()
    if not keys:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")

    key_data = keys[0]

    # Best-effort: update last_used_at (don't fail request if this fails)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(
                f"{SUPABASE_URL_FOR_AUTH}/rest/v1/api_keys",
                params={"id": f"eq.{key_data['id']}"},
                json={"last_used_at": "now()"},
                headers={
                    "apikey": SUPABASE_SERVICE_KEY_FOR_AUTH,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY_FOR_AUTH}",
                    "Content-Type": "application/json",
                },
            )
    except Exception:
        pass

    return key_data


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
def classify(req: ClassifyRequest, key_info=Depends(verify_api_key_optional)) -> ClassifyResponse:
    bundle = _bundle_for(req.multiclass)
    return _classify_single(req.text, bundle)


@app.post("/classify/batch", response_model=BatchClassifyResponse, tags=["inference"])
def classify_batch(req: BatchClassifyRequest, key_info=Depends(verify_api_key_optional)) -> BatchClassifyResponse:
    bundle = _bundle_for(req.multiclass)
    started = time.perf_counter()
    results = [_classify_single(text, bundle) for text in req.texts]
    total = (time.perf_counter() - started) * 1000.0
    return BatchClassifyResponse(
        results=results,
        total_latency_ms=round(total, 2),
        count=len(results),
    )
