"""ilk.medater Cloud — API (FastAPI). Servie derrière nginx sous /api (même origine que l'interface)."""
import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from . import __version__
from .config import get_settings
from .crud import build_router
from .db import SessionLocal
from .resources import RESOURCES
from .routers import admin, ai, auth, dashboard, directives, documents, legal, studies
from .security import CSRF_HEADER, limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

get_settings()  # échoue au démarrage si les secrets sont absents ou trop courts

app = FastAPI(title="ilk.medater Cloud API", version=__version__, docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None)
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    ip = request.client.host if request.client else "-"
    if not limiter.allow(f"ip:{ip}", get_settings().rate_limit_per_minute):
        return JSONResponse({"detail": "Trop de requêtes"}, status_code=429)
    # Protection CSRF : un site tiers ne peut pas ajouter d'en-tête personnalisé sans pré-vol CORS (refusé : aucune origine autorisée).
    if request.method in UNSAFE and request.url.path.startswith("/api/") and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse({"detail": "En-tête anti-CSRF manquant"}, status_code=403)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    with SessionLocal() as s:
        s.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}


for r in (auth.router, admin.router, dashboard.router, directives.router, studies.router, documents.router, legal.router, ai.router):
    api.include_router(r)
for res in RESOURCES:
    api.include_router(build_router(res))

app.include_router(api)
