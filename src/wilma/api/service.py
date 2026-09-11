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


import hashlib
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, HTTPException, Depends, Header, BackgroundTasks
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
SHORT_SUBFOLDER = "distilbert_v2"   # short-message model, used in the ensemble

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
    "short": None,
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

    print(f"[wilma-api] Loading short-message model from {HF_REPO}/{SHORT_SUBFOLDER}")
    try:
        _state["short"] = ModelBundle(HF_REPO, device, subfolder=SHORT_SUBFOLDER)
    except Exception as exc:  # the ensemble is optional; /classify must still work
        print(f"[wilma-api] short-message model unavailable: {exc}")
        _state["short"] = None

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
# Rate limiting
#
# In-memory sliding window. Buckets by API key when one is supplied,
# otherwise by client IP. Anonymous callers get a small allowance so the
# public demo cannot be hammered; keyed clients get a production allowance.
#
# Known limit: state lives in this process, so it resets on restart and
# would not hold across multiple replicas. Redis would be the fix if this
# ever scales beyond one container.
# ---------------------------------------------------------------------------

from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_ANONYMOUS = 30
RATE_LIMIT_WITH_KEY = 300
RATE_LIMIT_EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}

_request_log: dict[str, deque] = defaultdict(deque)
_last_sweep = time.time()


def _rate_limit_identity(request: Request) -> tuple[str, int]:
    """Return the bucket name for this caller and how many calls it may make."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            return f"key:{token[:12]}", RATE_LIMIT_WITH_KEY

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client = forwarded.split(",")[0].strip()
    else:
        client = request.client.host if request.client else "unknown"
    return f"ip:{client}", RATE_LIMIT_ANONYMOUS


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    global _last_sweep

    if request.url.path in RATE_LIMIT_EXEMPT_PATHS:
        return await call_next(request)

    bucket, allowance = _rate_limit_identity(request)
    now = time.time()
    hits = _request_log[bucket]

    # Drop anything that has fallen out of the window.
    while hits and now - hits[0] > RATE_LIMIT_WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= allowance:
        retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - hits[0])) + 1
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded.",
                "limit": allowance,
                "window_seconds": RATE_LIMIT_WINDOW_SECONDS,
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    hits.append(now)

    # Occasionally clear out buckets nobody is using, so the dict cannot
    # grow without bound as new IPs arrive.
    if now - _last_sweep > 300:
        for key in list(_request_log.keys()):
            queue = _request_log[key]
            while queue and now - queue[0] > RATE_LIMIT_WINDOW_SECONDS:
                queue.popleft()
            if not queue:
                del _request_log[key]
        _last_sweep = now

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(allowance)
    response.headers["X-RateLimit-Remaining"] = str(max(0, allowance - len(hits)))
    return response


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


def _hash_api_key(key: str) -> str:
    """SHA-256 of the raw key. Only the hash is stored, so a database leak
    does not expose usable customer credentials."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def _lookup_key(match: dict) -> Optional[dict]:
    """Find a live (non-revoked) api_keys row matching the given filter."""
    params = dict(match)
    params.update({
        "revoked_at": "is.null",
        "select": "id,user_id,name",
        "limit": "1",
    })
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{SUPABASE_URL_FOR_AUTH}/rest/v1/api_keys",
            params=params,
            headers={
                "apikey": SUPABASE_SERVICE_KEY_FOR_AUTH,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY_FOR_AUTH}",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Could not validate API key.")
    rows = response.json()
    return rows[0] if rows else None


async def _migrate_key_to_hash(key_id, key_hash: str) -> None:
    """Store the hash and clear the plaintext key. Best effort: a failure here
    must never break a customer request."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.patch(
                f"{SUPABASE_URL_FOR_AUTH}/rest/v1/api_keys",
                params={"id": f"eq.{key_id}"},
                json={"key_hash": key_hash, "key_full": None},
                headers={
                    "apikey": SUPABASE_SERVICE_KEY_FOR_AUTH,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY_FOR_AUTH}",
                    "Content-Type": "application/json",
                },
            )
        print(f"[wilma-api] migrated api key {key_id} to hashed storage")
    except Exception as exc:
        print(f"[wilma-api] key migration failed for {key_id}: {exc!r}")


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

    key_hash = _hash_api_key(key)

    try:
        key_data = await _lookup_key({"key_hash": f"eq.{key_hash}"})

        if key_data is None:
            # Legacy row: the key is still stored in plaintext. Accept it once,
            # then migrate it to a hash and erase the plaintext copy.
            key_data = await _lookup_key({"key_full": f"eq.{key}"})
            if key_data is not None:
                await _migrate_key_to_hash(key_data["id"], key_hash)
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Could not validate API key (auth service unreachable)."
        )

    if key_data is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key.")

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


@app.get("/api", tags=["meta"])
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
def classify(
    req: ClassifyRequest,
    background: BackgroundTasks,
    key_info=Depends(verify_api_key_optional),
) -> ClassifyResponse:
    bundle = _bundle_for(req.multiclass)
    result = _classify_single(req.text, bundle)

    if key_info:
        background.add_task(
            _record_usage,
            key_info["id"],
            key_info.get("user_id"),
            "/classify",
            1,
        )

    return result


@app.post("/classify/batch", response_model=BatchClassifyResponse, tags=["inference"])
def classify_batch(
    req: BatchClassifyRequest,
    background: BackgroundTasks,
    key_info=Depends(verify_api_key_optional),
) -> BatchClassifyResponse:
    bundle = _bundle_for(req.multiclass)
    started = time.perf_counter()
    results = [_classify_single(text, bundle) for text in req.texts]
    total = (time.perf_counter() - started) * 1000.0

    if key_info:
        background.add_task(
            _record_usage,
            key_info["id"],
            key_info.get("user_id"),
            "/classify/batch",
            len(req.texts),
        )

    return BatchClassifyResponse(
        results=results,
        total_latency_ms=round(total, 2),
        count=len(results),
    )

    # ---------------------------------------------------------------------------
# Usage metering
#
# Records that a call happened, from which key, to which endpoint, and how
# many messages it carried. Message content is never stored.
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone


async def _record_usage(
    api_key_id: str,
    user_id: Optional[str],
    endpoint: str,
    message_count: int,
) -> None:
    """Best effort usage write. Never raises into the request path."""
    if not SUPABASE_URL_FOR_AUTH or not SUPABASE_SERVICE_KEY_FOR_AUTH:
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{SUPABASE_URL_FOR_AUTH}/rest/v1/usage_events",
                json={
                    "api_key_id": str(api_key_id),
                    "user_id": str(user_id) if user_id else None,
                    "endpoint": endpoint,
                    "message_count": message_count,
                },
                headers={
                    "apikey": SUPABASE_SERVICE_KEY_FOR_AUTH,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY_FOR_AUTH}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
            )
    except Exception:
        pass


async def verify_api_key_required(key_info=Depends(verify_api_key_optional)):
    """Same as the optional check, but anonymous callers are rejected."""
    if key_info is None:
        raise HTTPException(
            status_code=401,
            detail="An API key is required for this endpoint. Use 'Bearer YOUR_API_KEY'.",
        )
    return key_info


class UsageResponse(BaseModel):
    period_days: int
    total_requests: int
    total_messages: int
    by_endpoint: dict[str, int]


@app.get("/usage", response_model=UsageResponse, tags=["meta"])
async def usage(days: int = 30, key_info=Depends(verify_api_key_required)) -> UsageResponse:
    """Return this API key's own usage over the last N days."""
    days = max(1, min(days, 365))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SUPABASE_URL_FOR_AUTH}/rest/v1/usage_events",
                params={
                    "api_key_id": f"eq.{key_info['id']}",
                    "created_at": f"gte.{since}",
                    "select": "endpoint,message_count",
                },
                headers={
                    "apikey": SUPABASE_SERVICE_KEY_FOR_AUTH,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY_FOR_AUTH}",
                },
            )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Usage service unreachable.")

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Could not read usage.")

    rows = response.json()
    by_endpoint: dict[str, int] = {}
    total_messages = 0

    for row in rows:
        endpoint = row.get("endpoint", "unknown")
        count = int(row.get("message_count") or 0)
        by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + count
        total_messages += count

    return UsageResponse(
        period_days=days,
        total_requests=len(rows),
        total_messages=total_messages,
        by_endpoint=by_endpoint,
    )

# ---------------------------------------------------------------------------
# Three-state verdict (ensemble of v1 and v2)
#
# v1 was trained on long-form email corpora and knows advance-fee and Nigerian
# prize language. v2 was trained on short-message smishing and knows
# credential harvesting. On the Nigerian evaluation set they fail on different
# messages, and between them they caught every scam.
#
#   both models flag  -> block   (highest precision)
#   exactly one flags -> review  (highest recall, send to a human)
#   neither flags     -> pass
#
# See docs/EVALUATION.md for the measurements behind this.
# ---------------------------------------------------------------------------

VERDICT_THRESHOLD = 0.5


class ModelOpinion(BaseModel):
    model_id: str
    is_scam: bool
    scam_probability: float


class VerdictResponse(BaseModel):
    verdict: str = Field(..., description="block, review or pass")
    action: str = Field(..., description="what the caller should do")
    agreement: str = Field(..., description="both, one or neither")
    models: list[ModelOpinion]
    latency_ms: float


def _scam_probability(text: str, bundle: "ModelBundle") -> float:
    enc = bundle.tokenizer(
        text, truncation=True, padding=True,
        max_length=MAX_LENGTH, return_tensors="pt",
    ).to(bundle.device)
    # DistilBERT's forward() has no token_type_ids argument, but the v1
    # tokenizer config emits one. Drop it rather than crash.
    enc.pop("token_type_ids", None)
    with torch.no_grad():
        probs = torch.softmax(bundle.model(**enc).logits, dim=1)[0]
    scam_idx = 1
    for idx, name in bundle.id2label.items():
        if str(name).strip().lower() == "scam":
            scam_idx = int(idx)
            break
    return float(probs[scam_idx])


@app.post("/verdict", response_model=VerdictResponse, tags=["inference"])
def verdict(
    req: ClassifyRequest,
    background: BackgroundTasks,
    key_info=Depends(verify_api_key_optional),
) -> VerdictResponse:
    """Three-state verdict from both models. Built for fraud operations:
    auto-block what both models agree on, queue the rest for a human."""
    try:
        return _verdict_impl(req, background, key_info)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[wilma-api] /verdict failed: {exc!r}")
        raise HTTPException(status_code=500, detail="Verdict failed. See server logs.")


def _verdict_impl(req, background, key_info) -> "VerdictResponse":
    start = time.perf_counter()

    binary = _state["binary"]
    short = _state["short"]
    if binary is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet")

    opinions: list[ModelOpinion] = []

    p1 = _scam_probability(req.text, binary)  # type: ignore[arg-type]
    opinions.append(ModelOpinion(
        model_id="distilbert_v1",
        is_scam=p1 >= VERDICT_THRESHOLD,
        scam_probability=round(p1, 4),
    ))

    if short is not None:
        p2 = _scam_probability(req.text, short)  # type: ignore[arg-type]
        opinions.append(ModelOpinion(
            model_id="distilbert_v2",
            is_scam=p2 >= VERDICT_THRESHOLD,
            scam_probability=round(p2, 4),
        ))

    flags = sum(1 for o in opinions if o.is_scam)

    if len(opinions) < 2:
        # Only one model available: never auto-block on a single opinion.
        agreement = "single_model"
        verdict_value = "review" if flags else "pass"
    elif flags == 2:
        agreement, verdict_value = "both", "block"
    elif flags == 1:
        agreement, verdict_value = "one", "review"
    else:
        agreement, verdict_value = "neither", "pass"

    action = {
        "block": "Block the message and notify the customer.",
        "review": "Models disagree. Send to a human review queue.",
        "pass": "No fraud signal. Deliver normally.",
    }[verdict_value]

    if key_info:
        background.add_task(
            _record_usage,
            key_info["id"],
            key_info.get("user_id"),
            "/verdict",
            1,
        )

    return VerdictResponse(
        verdict=verdict_value,
        action=action,
        agreement=agreement,
        models=opinions,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )


# ---------------------------------------------------------------------------
# Demo front end. Mounted last: a StaticFiles mount at "/" is a catch-all and
# would shadow every route declared after it.
# ---------------------------------------------------------------------------
from fastapi.staticfiles import StaticFiles  # noqa: E402

_STATIC_DIR = Path(__file__).resolve().parents[3] / "static"
if not _STATIC_DIR.is_dir():
    _STATIC_DIR = Path("/app/static")

if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
    print(f"[wilma-api] serving demo page from {_STATIC_DIR}")
else:
    print("[wilma-api] no static directory found; \"/\" will 404")

# ---------------------------------------------------------------------------
# Static asset caching and a human 404 page. Declared after the mount so
# that _STATIC_DIR is already resolved.
# ---------------------------------------------------------------------------
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

_API_PREFIXES = (
    "/classify", "/verdict", "/usage", "/health", "/api",
    "/docs", "/redoc", "/openapi.json",
)
_LONG_CACHE = (".css", ".svg", ".png", ".jpg", ".webp", ".woff2", ".ico")


@app.middleware("http")
async def static_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.endswith(_LONG_CACHE):
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "public, max-age=300, must-revalidate"
    return response


@app.exception_handler(StarletteHTTPException)
async def not_found_handler(request: Request, exc: StarletteHTTPException):
    wants_html = "text/html" in request.headers.get("accept", "")
    is_api = request.url.path.startswith(_API_PREFIXES)
    if exc.status_code == 404 and wants_html and not is_api:
        page = _STATIC_DIR / "404.html"
        if page.is_file():
            return FileResponse(str(page), status_code=404)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


