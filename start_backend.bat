@echo off
title FORGE-VISION — Backend Server
echo.
echo ============================================================
echo   FORGE-VISION Forensic Intelligence Platform
echo   Backend API Server (FastAPI + Python)
echo   SIH Problem Statement 150
echo ============================================================
echo.

cd /d "%~dp0backend"

echo [1/3] Seeding demo database...
python seed.py
if %errorlevel% neq 0 (
    echo WARNING: Seed failed - database may already be seeded or Python not in PATH
)

echo.
echo [2/3] Starting FastAPI server on http://localhost:8000
echo       API docs: http://localhost:8000/docs
echo.
echo [3/3] Press Ctrl+C to stop
echo.

python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

pause
