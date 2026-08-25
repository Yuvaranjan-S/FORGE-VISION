@echo off
title FORGE-VISION — Frontend Server
echo.
echo ============================================================
echo   FORGE-VISION Forensic Intelligence Platform
echo   Frontend (Next.js React)
echo   SIH Problem Statement 150
echo ============================================================
echo.

cd /d "%~dp0frontend"

echo [1/2] Installing dependencies (first run only)...
npm install --silent

echo.
echo [2/2] Starting Next.js dev server on http://localhost:3000
echo.

npm run dev

pause
