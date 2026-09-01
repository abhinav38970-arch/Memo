"""
SchemaMind API — FastAPI backend.
Deployed on Render. Uses Groq for LLM inference.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import health, patterns, quiz, adaptation
from app.services.groq_client import GroqClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate Groq connection
    client = GroqClient()
    ok = await client.health_check()
    if not ok:
        print("⚠️  WARNING: Groq API not reachable. Check your API key.")
    else:
        print("✅ Groq API connected.")
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="SchemaMind API",
    description="AI-powered pattern-based memorization backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend on any domain during hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Normalize duplicate slashes in paths (e.g. "//api/x" from a frontend
# configured with a trailing-slash API URL) so they don't 404.
@app.middleware("http")
async def collapse_double_slashes(request, call_next):
    path = request.scope.get("path", "")
    if "//" in path:
        import re
        request.scope["path"] = re.sub(r"/{2,}", "/", path)
    return await call_next(request)

# Routers
app.include_router(health.router)
app.include_router(patterns.router)
app.include_router(quiz.router)
app.include_router(adaptation.router)


@app.get("/")
async def root():
    return {
        "app": "SchemaMind API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }