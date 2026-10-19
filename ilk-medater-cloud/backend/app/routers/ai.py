"""API ilk.medater AI : catalogue, consentement, question, historique personnel."""
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.assistants import ASSISTANTS
from ..ai.engine import answer
from ..ai.providers import ollama_available
from ..audit import audit
from ..authz import Principal
from ..config import get_settings
from ..db import get_db
from ..deps import client_ip, current
from ..models import AiConsent, AiRequest
from ..security import limiter

router = APIRouter(prefix="/ai", tags=["ai"])

POLICY_TEXT = (
    "En activant l'IA cloud pour une demande, vous acceptez que la question et les extraits de données autorisés, "
    "après masquage automatique des emails, téléphones, NIF et RIB, soient transmis au fournisseur configuré. "
    "Les données financières, RH et les documents confidentiels ne sont jamais transmis. Ne saisissez pas de "
    "secret ni de donnée personnelle dans la question. Les transferts de données hors d'Algérie doivent être "
    "validés au préalable par la Direction et le juriste du groupe."
)


class AskIn(BaseModel):
    assistant: str = Field(max_length=40)
    question: Annotated[str, Field(min_length=3, max_length=2000)]
    company_id: Optional[int] = None
    project_id: Optional[int] = None
    engine: Literal["auto", "local", "cloud"] = "auto"
    cloud_consent: bool = False


@router.get("/status")
def status(p: Principal = Depends(current)):
    cfg = get_settings()
    return {"local_enabled_for_you": p.ai_local, "cloud_enabled_for_you": p.ai_cloud,
            "local_model_available": ollama_available(), "local_model": cfg.ollama_model if cfg.ollama_url else None,
            "cloud_configured": cfg.cloud_configured, "cloud_model": cfg.cloud_ai_model if cfg.cloud_configured else None,
            "policy_version": cfg.ai_policy_version, "policy_text": POLICY_TEXT}


@router.get("/assistants")
def assistants(p: Principal = Depends(current)):
    return [{"code": a.code, "name": a.name, "org_unit": a.org_unit, "focus": a.focus, "engines": a.engines,
             "modules": a.modules, "available": any(p.has_module_anywhere(m) for m in a.modules)} for a in ASSISTANTS.values()]


@router.post("/consent")
def consent(request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    if not p.ai_cloud:
        raise HTTPException(403, "IA cloud non autorisée pour votre compte")
    v = get_settings().ai_policy_version
    s.add(AiConsent(user_id=p.id, policy_version=v))
    audit(s, p.id, "ai.consent", f"user:{p.id}", details={"policy_version": v}, ip=client_ip(request))
    s.commit()
    return {"status": "ok", "policy_version": v}


@router.post("/ask")
def ask(data: AskIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    if not (p.ai_local or p.ai_cloud):
        raise HTTPException(403, "ilk.medater AI n'est pas activée pour votre compte (décision du Directeur général)")
    a = ASSISTANTS.get(data.assistant)
    if not a:
        raise HTTPException(404, "Assistant inconnu")
    if not any(p.has_module_anywhere(m) for m in a.modules):
        raise HTTPException(403, "Cet assistant n'a accès à aucune donnée de votre périmètre")
    if not limiter.allow(f"ai:{p.id}", 20):
        raise HTTPException(429, "Trop de demandes, patientez une minute")
    res = answer(s, p, a, data.question, data.company_id, data.project_id, data.engine, data.cloud_consent)
    sources = [{"id": x.id, "type": x.type, "ref": x.ref, "label": x.label} for x in res.sources]
    row = AiRequest(user_id=p.id, assistant_code=a.code, engine=res.engine, company_id=data.company_id,
                    project_id=data.project_id, question=data.question, answer=res.answer, sources=sources,
                    redactions=res.redactions)
    s.add(row)
    s.flush()
    audit(s, p.id, "ai.ask", f"ai_request:{row.id}", company_id=data.company_id,
          details={"assistant": a.code, "engine": res.engine, "sources": [x["ref"] for x in sources],
                   "redactions": res.redactions}, ip=client_ip(request))
    s.commit()
    return {"id": row.id, "assistant": a.code, "engine": res.engine, "answer": res.answer, "sources": sources,
            "missing_information": res.missing, "notices": res.notices}


@router.get("/history")
def history(p: Principal = Depends(current), s: Session = Depends(get_db)):
    rows = s.scalars(select(AiRequest).where(AiRequest.user_id == p.id).order_by(AiRequest.id.desc()).limit(50))
    return [{"id": r.id, "assistant": r.assistant_code, "engine": r.engine, "question": r.question, "answer": r.answer,
             "sources": r.sources, "created_at": r.created_at} for r in rows]
