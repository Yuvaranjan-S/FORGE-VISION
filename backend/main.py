"""
FORGE-VISION — FastAPI Production Server Entry Point
Can be launched via:
  - Local dev: python main.py
  - Production (Render): uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=not is_prod,
        access_log=True,
    )
