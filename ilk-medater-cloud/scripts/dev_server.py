"""Serveur de développement SANS Docker : API + interface sur la même origine (remplace nginx en local).

Usage (depuis backend/) :
  DATABASE_URL=... MIGRATION_DATABASE_URL=... SESSION_SECRET=... MFA_ENCRYPTION_KEY=... \
  python ../scripts/dev_server.py --port 8080
Réservé au développement : en production, utiliser docker compose (nginx, en-têtes CSP, limitation de débit).
"""
import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port)
