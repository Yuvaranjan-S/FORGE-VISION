"""
FORGE-VISION — FastAPI Backend Entry Point
Production-ready configuration for local development and cloud deployment (Render).
"""
import os
import sys
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db, check_database_connection
from .routers import (
    auth,
    cases,
    evidence,
    acquisition,
    analysis,
    custody,
    reporting,
    nlp,
    timeline,
    datasets,
    bookmarks,
    cameras,
    audit,
    kaggle,
)

# Resolve robust absolute directory paths
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, "..", ".."))
EVIDENCE_STORE_DIR = os.path.join(PROJECT_ROOT, "evidence_store")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure evidence_store and data directories exist safely
    os.makedirs(os.path.join(EVIDENCE_STORE_DIR, "files"), exist_ok=True)
    os.makedirs(os.path.join(EVIDENCE_STORE_DIR, "thumbnails"), exist_ok=True)
    os.makedirs(os.path.join(EVIDENCE_STORE_DIR, "reports"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "datasets"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "kaggle"), exist_ok=True)
    
    await init_db()
    yield


app = FastAPI(
    title="FORGE-VISION Forensic API",
    description="Vendor-Agnostic DVR/NVR Forensic Intelligence & Evidence Reconstruction Platform",
    version="1.0.0-SIH150",
    lifespan=lifespan,
)

# ── DYNAMIC CORS CONFIGURATION ───────────────────────────────────────────────
frontend_url_env = os.getenv("FRONTEND_URL", "").strip()
cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
]

if frontend_url_env:
    for url in frontend_url_env.split(","):
        cleaned = url.strip().rstrip("/")
        if cleaned:
            origins.append(cleaned)

if cors_origins_env:
    for url in cors_origins_env.split(","):
        cleaned = url.strip().rstrip("/")
        if cleaned:
            origins.append(cleaned)

allowed_origins = sorted(list(set(origins)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── ROUTERS ──────────────────────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/auth",        tags=["Authentication"])
app.include_router(cases.router,       prefix="/api/cases",       tags=["Cases"])
app.include_router(datasets.router,    prefix="/api/datasets",    tags=["Dataset Library"])
app.include_router(kaggle.router,      prefix="/api/kaggle",      tags=["Kaggle Dataset Pipeline"])
app.include_router(evidence.router,    prefix="/api/evidence",    tags=["Evidence"])
app.include_router(acquisition.router, prefix="/api/acquisition", tags=["Acquisition"])
app.include_router(analysis.router,    prefix="/api/analysis",    tags=["Analysis"])
app.include_router(custody.router,     prefix="/api/custody",     tags=["Chain of Custody"])
app.include_router(reporting.router,   prefix="/api/reporting",   tags=["Reporting"])
app.include_router(nlp.router,         prefix="/api/nlp",         tags=["NLP Query"])
app.include_router(timeline.router,    prefix="/api/timeline",    tags=["Timeline"])
app.include_router(bookmarks.router,   prefix="/api/bookmarks",   tags=["Evidence Bookmarks"])
app.include_router(cameras.router,     prefix="/api/cameras",     tags=["Camera Topology"])
app.include_router(audit.router,       prefix="/api/audit",       tags=["Audit Logs"])


# ── HEALTH & STATUS ENDPOINTS ────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health():
    env = os.getenv("ENVIRONMENT", "development").lower()
    return {
        "status": "ok",
        "service": "forge-vision-backend",
        "environment": env,
    }


@app.get("/health/dependencies", tags=["Health"])
@app.get("/api/health/dependencies", tags=["Health"])
async def health_dependencies():
    db_connected = await check_database_connection()
    ffmpeg_available = shutil.which("ffmpeg") is not None
    ffprobe_available = shutil.which("ffprobe") is not None
    
    opencv_available = False
    try:
        import cv2
        opencv_available = True
    except Exception:
        opencv_available = False

    return {
        "status": "ok",
        "python": sys.version.split()[0],
        "database": "connected" if db_connected else "disconnected",
        "ffmpeg": "available" if ffmpeg_available else "unavailable",
        "ffprobe": "available" if ffprobe_available else "unavailable",
        "opencv": "available" if opencv_available else "unavailable",
    }
