# FORGE-VISION
## Multi-Vendor DVR/NVR Forensic Intelligence & Evidence Reconstruction Platform
### Smart India Hackathon (SIH) — Problem Statement 150

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-black.svg?style=flat&logo=next.js)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776ab.svg?style=flat&logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178c6.svg?style=flat&logo=typescript)](https://typescriptlang.org)
[![Digital Forensics](https://img.shields.io/badge/Forensics-Triple%20Hash%20%7C%20Section%2065B%20%7C%20BSA%202023-amber.svg)](https://github.com)

---

## 🎯 Executive Summary
**FORGE-VISION** is an end-to-end, vendor-agnostic digital forensics intelligence and video reconstruction workstation designed for law enforcement, judicial agencies, and forensic examiners.

Surveillance infrastructure in India and worldwide is fragmented across numerous proprietary DVR/NVR vendors (Hikvision, Dahua, CP Plus, Matrix, Uniview, Honeywell, Godrej, TP-Link). Each vendor uses proprietary containers, non-standard timestamps, disparate timezones, and closed filesystem structures.

**FORGE-VISION solves this by providing:**
1. **Universal Evidence Ingestion & Write-Blocking**: Master evidence is preserved read-only with cryptographic triple-hashing (`MD5`, `SHA-256`, `SHA3-256`).
2. **Modular Vendor Adapter Framework**: Open pluggable architecture normalizing proprietary streams into a unified Common Evidence Model.
3. **Dataset Provenance Registry**: Clear tracking for public research benchmarks (UCF Crime, VIRAT, RACD, Traffic), authorized CCTV exports, vendor samples, and synthetic evaluation suites.
4. **CAM / Camera Management & Stream Verification**: Automated scan-and-import pipeline from dataset libraries into individual camera feeds with real SHA-256 calculation and FFprobe metadata.
5. **Stream Recovery & Continuity Analysis**: H.264/H.265 NAL unit continuity scanning, recording gap analysis, and partial reconstructability scoring.
6. **Multi-Camera Spatial Correlation & Timeline Sync**: Dual-timestamp normalization, spatial camera network mapping, and cross-camera suspect transition tracking.
7. **Assistive Forensic AI & Tamper Detection**: Grounded YOLO object detection, Error Level Analysis (ELA), frame duplication detection, and camera blackout alerts.
8. **Tamper-Evident Chain-of-Custody Ledger**: Blockchain-style SHA-256 hash-chained custody tracking with 1-click verification.
9. **Court-Ready Legal Reporting**: Automatic PDF generation containing Section 65B Indian Evidence Act / **Bharatiya Sakshya Adhiniyam, 2023 (BSA 2023)** Electronic Record Certificates.

---

## 🏗 Architecture

```
                               ┌────────────────────────┐
                               │   Forensic Examiner    │
                               └───────────┬────────────┘
                                           │ HTTPS
                                           ▼
                       ┌────────────────────────────────────────┐
                       │          VERCEL FRONTEND               │
                       │     (Next.js 16 + React 19 UI)         │
                       └───────────────────┬────────────────────┘
                                           │ REST API / JWT
                                           ▼
                       ┌────────────────────────────────────────┐
                       │           RENDER BACKEND               │
                       │       (FastAPI Forensic API)           │
                       └───────────┬────────────────┬───────────┘
                                   │                │
            ┌──────────────────────┴───────┐  ┌─────┴──────────────────────┐
            ▼                              ▼  ▼                            ▼
┌──────────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│   Database Engine    │ │  Crypto Hashing  │ │ Forensic Parsers │ │ AI & Verification│
│ (SQLite / PostgreSQL)│ │(MD5,SHA256,SHA3) │ │ (FFprobe, OpenCV)│ │(YOLO, ELA, Tamper│
└──────────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
```

---

## 💻 Local Development Setup

### 1. Backend (FastAPI)
```powershell
# Navigate to backend directory
cd backend

# Create virtual environment (optional)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend server (runs at http://localhost:8000)
python main.py
```
*API Swagger Documentation:* `http://localhost:8000/docs`  
*Health Check:* `http://localhost:8000/health`  
*Dependency Status:* `http://localhost:8000/health/dependencies`

### 2. Frontend (Next.js)
```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run frontend dev server (runs at http://localhost:3000)
npm run dev
```
*Web Application:* `http://localhost:3000`

---

## 🔑 Demo Accounts & RBAC Roles

| Role | Username | Password | Permissions |
|---|---|---|---|
| **Lead Investigator** | `admin` | `admin123` | Full forensic suite (Ingestion, Analysis, Custody, Datasets) |
| **Investigator** | `investigator` | `inv123` | Ingest evidence, run analytics, create bookmarks, query evidence |
| **Auditor** | `auditor` | `audit123` | Read-only oversight, verify cryptographic hash chains, inspect audit logs |

---

## ☁️ Complete Cloud Deployment Guide

### STEP 1: Push Project to GitHub

1. Initialize Git repository and add files:
```powershell
git init -b main
git add .
git commit -m "Initial production-ready FORGE-VISION deployment"
```
2. Create a new GitHub repository (e.g. `https://github.com/<your-username>/FORGE-VISION`).
3. Push to GitHub:
```powershell
git remote add origin https://github.com/<your-username>/FORGE-VISION.git
git push -u origin main
```

*(Note: `.gitignore` automatically prevents CCTV video files, databases, cache, and `.env` secrets from being uploaded).*

---

### STEP 2: Deploy Backend to Render

1. Log into [Render.com](https://render.com).
2. Click **New +** → **Web Service**.
3. Connect your GitHub repository: `FORGE-VISION`.
4. Configure the Web Service:
   - **Name:** `forge-vision-backend`
   - **Root Directory:** `backend`
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `ENVIRONMENT` = `production`
   - `PYTHON_VERSION` = `3.11.9`
   - `FRONTEND_URL` = `https://<your-vercel-app>.vercel.app` *(update after Step 3)*
   - `CORS_ORIGINS` = `https://<your-vercel-app>.vercel.app,http://localhost:3000`
   - `DATABASE_URL` = `sqlite:///./db/forensiq.db` *(or PostgreSQL connection string)*
6. Click **Deploy Web Service**.
7. Once deployed, note down your Render URL: e.g. `https://forge-vision-backend.onrender.com`.
8. Verify backend health by visiting: `https://forge-vision-backend.onrender.com/health`

---

### STEP 3: Deploy Frontend to Vercel

1. Log into [Vercel.com](https://vercel.com).
2. Click **Add New...** → **Project**.
3. Import your GitHub repository: `FORGE-VISION`.
4. Configure the Project:
   - **Framework Preset:** `Next.js`
   - **Root Directory:** Click **Edit** and select `frontend`.
   - **Build Command:** `npm run build`
   - **Output Directory:** `.next`
5. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_API_URL` = `https://<your-render-backend>.onrender.com`
6. Click **Deploy**.
7. Once deployed, note down your Vercel URL: e.g. `https://forge-vision.vercel.app`.

---

### STEP 4: Update CORS on Render & Connect

1. Return to your **Render Backend Dashboard** → **Environment Variables**.
2. Update `FRONTEND_URL` to your Vercel URL: `https://forge-vision.vercel.app`
3. Update `CORS_ORIGINS` to: `https://forge-vision.vercel.app,http://localhost:3000`
4. Click **Save Changes** (Render will automatically redeploy).
5. Open your Vercel URL and test login, evidence exploration, and dataset video importing.

---

## ⚖️ Forensic Safeguards & Production Limitations

1. **Large CCTV Storage:** Large surveillance binary files should never be committed to Git. In a full production deployment, evidence files must be stored in secure S3/Blob storage with immutable object locking (WORM).
2. **Database Persistence:** SQLite is configured for local evaluation and prototype demonstrations. For continuous cloud production across ephemeral instances, PostgreSQL is recommended.
3. **FFmpeg Availability:** Video transcoding and metadata extraction use FFmpeg/FFprobe when available, with graceful fallback if uninstalled.
4. **Provenance Integrity:** Public research datasets (VIRAT, UCF Crime) are strictly classified as `PUBLIC_RESEARCH_DATASET` with `Vendor: Unknown` to prevent misrepresentation.
5. **Simulated OEM Adapters:** Demonstration and proprietary carvers without physical hardware access are labeled as `* SIMULATED VENDOR DATA`.

---

## 👥 Authors
Built for **Smart India Hackathon (SIH)** — Problem Statement 150.  
Platform: **FORGE-VISION** — Forensic Video Intelligence & Evidence Reconstruction Platform.
