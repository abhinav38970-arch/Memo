"""
SchemaMind API — FastAPI backend.
Deployed on Render. Uses Groq for LLM inference.
"""
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import adaptation, health, patterns, quiz
from app.services.groq_client import GroqClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate Groq connection and print the effective configuration
    # so misconfigured deploys are obvious from the logs.
    client = GroqClient()
    config = client.describe()
    print(
        f"[groq] model={config['model']} tpm_limit={config['tpm_limit']} "
        f"max_completion_tokens={config['max_completion_tokens']} reasoning={config['reasoning']}",
        flush=True,
    )
    ok = await client.health_check()
    if not ok:
        print("⚠️  WARNING: Groq API not reachable. Check your API key.", flush=True)
    else:
        print("✅ Groq API connected.", flush=True)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="SchemaMind API",
    description="AI-powered pattern-based memorization backend",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend on any domain during hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Let the browser read the rate-limit countdown on 429 responses.
    expose_headers=["Retry-After"],
)


# Normalize duplicate slashes in paths (e.g. "//api/x" from a frontend
# configured with a trailing-slash API URL) so they don't 404.
@app.middleware("http")
async def collapse_double_slashes(request: Request, call_next):
    path = request.scope.get("path", "")
    if "//" in path:
        request.scope["path"] = re.sub(r"/{2,}", "/", path)
    return await call_next(request)


_FIELD_LABELS = {
    "text": "The text to memorize",
    "original_text": "The text to memorize",
    "preferences": "Your pattern preferences",
    "patterns": "The patterns",
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Turn pydantic's 422 payload into one readable sentence.

    The frontend shows ``detail`` verbatim, so "The text to memorize must be
    at least 10 characters" beats a JSON dump of ``ctx``/``loc``/``input``.
    """
    messages = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        field = loc[0] if loc else "request"
        label = _FIELD_LABELS.get(field, field.replace("_", " ").capitalize())
        etype = err.get("type", "")
        ctx = err.get("ctx") or {}
        if etype == "string_too_short":
            msg = f"{label} must be at least {ctx.get('min_length')} characters."
        elif etype == "string_too_long":
            msg = f"{label} must be at most {ctx.get('max_length'):,} characters — please shorten it."
        elif etype == "too_short":
            msg = f"{label} must contain at least {ctx.get('min_length')} item(s)."
        elif etype == "too_long":
            msg = f"{label} may contain at most {ctx.get('max_length')} item(s)."
        elif etype == "missing":
            msg = f"{label} is required."
        else:
            msg = f"{label}: {err.get('msg', 'invalid value')}."
        if msg not in messages:
            messages.append(msg)
    detail = " ".join(messages) or "Invalid request."
    print(f"[api] 422 {request.method} {request.url.path}: {detail}", flush=True)
    return JSONResponse(status_code=422, content={"detail": detail})


# Routers
app.include_router(health.router)
app.include_router(patterns.router)
app.include_router(quiz.router)
app.include_router(adaptation.router)


@app.get("/")
async def root():
    return {
        "app": "SchemaMind API",
        "version": "1.1.0",
        "docs": "/docs",
        "status": "running",
    }
