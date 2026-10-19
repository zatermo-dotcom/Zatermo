"""Études : livrables par phase et spécialité (circuit de validation), moteurs de calcul tracés."""
from datetime import date
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..authz import Principal
from ..crud import row_dict
from ..db import get_db
from ..deps import client_ip, current
from ..engines.calcs import ENGINES
from ..models import CalcRun, Deliverable, Document, Project
from ..resources import DISCIPLINES

router = APIRouter(prefix="/studies", tags=["studies"])

PHASES = ("ESQ", "APS", "APD", "DCE", "EXE", "DOE")
# Livrables types proposés par spécialité (canevas de départ, modifiable par projet).
TEMPLATES = {
    "ARCH": ["Programme et tableau des surfaces", "Plans, coupes et façades", "Notice descriptive", "Dossier de permis de construire"],
    "GC": ["Hypothèses et descente de charges", "Note de calcul structure", "Plans de coffrage et ferraillage", "Métré structure"],
    "CFO": ["Bilan de puissance", "Schémas unifilaires TGBT/TD", "Note de calcul câbles et protections", "Plans éclairage et prises"],
    "CFA": ["Architecture réseau VDI", "Synoptique vidéosurveillance et contrôle d'accès", "Plans de câblage", "Interphonie"],
    "FIRE": ["Notice de sécurité incendie", "Plans détection et alarme", "Implantation extincteurs/RIA", "Note sprinklers (si requise)"],
    "PLUMB": ["Note de calcul EF/ECS", "Schéma d'évacuation EU/EV/EP", "Surpression et réservoirs", "Plans plomberie"],
    "HVAC": ["Bilan thermique", "Sélection préliminaire des équipements", "Schéma de principe CVC", "Régulation"],
    "AIR": ["Note de renouvellement d'air", "Dimensionnement des gaines", "Pertes de charge et équilibrage", "Plans aérauliques"],
    "COORD": ["Synthèse BIM MEP", "Plan de réservations", "Registre des conflits", "PV de coordination"],
    "LEGAL": ["Analyse du CCAP/CCAG", "Suivi ODS et avenants", "Mémoire de réclamation"],
}


class DeliverableIn(BaseModel):
    model_config = {"extra": "forbid"}
    project_id: int
    discipline: Literal[DISCIPLINES]  # type: ignore[valid-type]
    phase: Literal[PHASES]  # type: ignore[valid-type]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    due_date: Optional[date] = None
    document_id: Optional[int] = None


class ReviewIn(BaseModel):
    decision: Literal["valide", "rejete"]
    comment: Annotated[str, Field(max_length=2000)] = ""


class CalcIn(BaseModel):
    project_id: int
    inputs: dict
    save: bool = True


def _project(s: Session, pid: int) -> Project:
    p = s.get(Project, pid)
    if not p:
        raise HTTPException(404, "Projet introuvable")
    return p


@router.get("/catalog")
def catalog(p: Principal = Depends(current)):
    return {"phases": PHASES, "templates": TEMPLATES,
            "engines": [{"code": e.code, "name": e.name, "discipline": e.discipline, "version": e.version,
                         "method": e.method, "references": e.references, "schema": e.input_model.model_json_schema()}
                        for e in ENGINES.values()]}


@router.get("/deliverables")
def list_deliverables(project_id: Optional[int] = None, discipline: Optional[str] = None,
                      p: Principal = Depends(current), s: Session = Depends(get_db)):
    q = select(Deliverable).where(p.scope_clause(Deliverable, "studies")).order_by(Deliverable.phase, Deliverable.discipline, Deliverable.id)
    if project_id:
        q = q.where(Deliverable.project_id == project_id)
    if discipline:
        q = q.where(Deliverable.discipline == discipline)
    return [row_dict(d) for d in s.scalars(q)]


@router.post("/deliverables", status_code=201)
def create_deliverable(data: DeliverableIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    proj = _project(s, data.project_id)
    p.require("studies", "edit", proj.company_id, proj.id)
    if data.document_id:
        doc = s.get(Document, data.document_id)
        if not doc or doc.company_id != proj.company_id:
            raise HTTPException(422, "Document introuvable dans la filiale du projet")
    d = Deliverable(**data.model_dump(), company_id=proj.company_id, author_id=p.id)
    s.add(d)
    s.flush()
    audit(s, p.id, "deliverable.created", f"deliverable:{d.id}", company_id=proj.company_id, ip=client_ip(request))
    s.commit()
    return row_dict(d)


@router.post("/deliverables/{did}/submit")
def submit(did: int, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    d = s.get(Deliverable, did)
    if not d:
        raise HTTPException(404, "Livrable introuvable")
    p.require("studies", "edit", d.company_id, d.project_id)
    if d.status not in ("brouillon", "rejete"):
        raise HTTPException(409, f"Livrable déjà {d.status}")
    from ..security import now
    d.status, d.submitted_at = "soumis", now()
    audit(s, p.id, "deliverable.submitted", f"deliverable:{d.id}", company_id=d.company_id, ip=client_ip(request))
    s.commit()
    return row_dict(d)


@router.post("/deliverables/{did}/review")
def review(did: int, data: ReviewIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    d = s.get(Deliverable, did)
    if not d:
        raise HTTPException(404, "Livrable introuvable")
    p.require("studies", "validate", d.company_id, d.project_id)
    if d.status != "soumis":
        raise HTTPException(409, "Seul un livrable soumis peut être validé ou rejeté")
    if d.author_id == p.id and not p.is_director:
        raise HTTPException(403, "Principe des quatre yeux : l'auteur ne peut pas valider son propre livrable")
    if data.decision == "rejete" and not data.comment.strip():
        raise HTTPException(422, "Motif de rejet obligatoire")
    from ..security import now
    d.status, d.validator_id, d.validated_at, d.review_comment = data.decision, p.id, now(), data.comment
    audit(s, p.id, f"deliverable.{data.decision}", f"deliverable:{d.id}", company_id=d.company_id,
          details={"comment": data.comment}, ip=client_ip(request))
    s.commit()
    return row_dict(d)


@router.post("/calc/{engine_code}")
def run_engine(engine_code: str, data: CalcIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    eng = ENGINES.get(engine_code)
    if not eng:
        raise HTTPException(404, "Moteur inconnu")
    proj = _project(s, data.project_id)
    p.require("studies", "edit" if data.save else "view", proj.company_id, proj.id)
    try:
        parsed = eng.input_model.model_validate(data.inputs)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))
    res = eng.run(parsed)
    out = {"engine": eng.code, "engine_version": eng.version, "method": eng.method, "references": eng.references,
           "inputs": parsed.model_dump(), **res}
    if data.save:
        run = CalcRun(project_id=proj.id, company_id=proj.company_id, engine=eng.code, engine_version=eng.version,
                      inputs=parsed.model_dump(mode="json"), outputs=res["outputs"], warnings=res["warnings"], author_id=p.id)
        s.add(run)
        s.flush()
        audit(s, p.id, "calc.run", f"calc:{run.id}", company_id=proj.company_id, details={"engine": eng.code}, ip=client_ip(request))
        s.commit()
        out["id"] = run.id
    return out


@router.get("/calc-runs")
def calc_runs(project_id: Optional[int] = None, p: Principal = Depends(current), s: Session = Depends(get_db)):
    q = select(CalcRun).where(p.scope_clause(CalcRun, "studies")).order_by(CalcRun.id.desc()).limit(200)
    if project_id:
        q = q.where(CalcRun.project_id == project_id)
    return [row_dict(r) for r in s.scalars(q)]
