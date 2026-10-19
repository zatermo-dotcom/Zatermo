"""Base des références juridiques vérifiées (droit algérien, marchés publics, urbanisme, construction).

Le logiciel n'embarque aucun texte de loi : chaque référence est saisie par un juriste à partir de la source
officielle (Journal officiel, site institutionnel) puis marquée « vérifiée » par un utilisateur disposant de
l'action « validate ». L'assistant juridique ne cite que des références vérifiées et en vigueur.
"""
from datetime import date
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit import audit
from ..authz import Principal
from ..crud import row_dict
from ..db import get_db
from ..deps import client_ip, current
from ..models import LegalSource
from ..security import now

router = APIRouter(prefix="/legal", tags=["legal"])

TextType = Literal["loi", "ordonnance", "decret_presidentiel", "decret_executif", "arrete", "instruction", "circulaire",
                   "cahier_des_charges", "jurisprudence", "autre"]


class LegalIn(BaseModel):
    model_config = {"extra": "forbid"}
    text_type: TextType
    title: Annotated[str, Field(min_length=5, max_length=400)]
    reference_number: Annotated[str, Field(min_length=1, max_length=80)]
    article: Annotated[str, Field(max_length=80)] = ""
    publication_date: Optional[date] = None
    jo_reference: Annotated[str, Field(max_length=120)] = ""
    version_label: Annotated[str, Field(max_length=120)] = ""
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    source_url: Annotated[str, Field(max_length=500)] = ""
    excerpt: Annotated[str, Field(max_length=8000)] = ""
    keywords: list[Annotated[str, Field(max_length=60)]] = Field(default_factory=list, max_length=30)


def _require(p: Principal, action: str) -> None:
    if not p.has_module_anywhere("legal", action):
        raise HTTPException(403, "Accès refusé : base juridique non autorisée")


def legal_status(src: LegalSource) -> str:
    if not src.verified_at:
        return "non_verifiee"
    if src.valid_to and src.valid_to < date.today():
        return "abrogee_ou_expiree"
    return "verifiee"


def search_sources(s: Session, terms: list[str], only_verified: bool = True, limit: int = 8) -> list[LegalSource]:
    q = select(LegalSource)
    if only_verified:
        q = q.where(LegalSource.verified_at.is_not(None),
                    or_(LegalSource.valid_to.is_(None), LegalSource.valid_to >= date.today()))
    conds = []
    for t in terms:
        like = f"%{t}%"
        conds += [LegalSource.title.ilike(like), LegalSource.excerpt.ilike(like), LegalSource.reference_number.ilike(like),
                  LegalSource.keywords.any(t.lower())]
    if conds:
        q = q.where(or_(*conds))
    return list(s.scalars(q.order_by(LegalSource.publication_date.desc().nulls_last()).limit(limit)))


def _out(src: LegalSource) -> dict:
    d = row_dict(src)
    d["status"] = legal_status(src)
    return d


@router.get("/sources")
def list_sources(q: Optional[str] = None, p: Principal = Depends(current), s: Session = Depends(get_db)):
    _require(p, "view")
    if q:
        return [_out(x) for x in search_sources(s, [w for w in q.split() if len(w) > 2][:6], only_verified=False, limit=100)]
    return [_out(x) for x in s.scalars(select(LegalSource).order_by(LegalSource.id.desc()).limit(500))]


@router.post("/sources", status_code=201)
def create_source(data: LegalIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    _require(p, "edit")
    src = LegalSource(**data.model_dump(), created_by=p.id)
    s.add(src)
    s.flush()
    audit(s, p.id, "legal.created", f"legal:{src.id}", ip=client_ip(request))
    s.commit()
    return _out(src)


@router.post("/sources/{sid}/verify")
def verify_source(sid: int, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    _require(p, "validate")
    src = s.get(LegalSource, sid)
    if not src:
        raise HTTPException(404, "Référence introuvable")
    if not (src.source_url or src.jo_reference):
        raise HTTPException(422, "Une source officielle (URL ou référence du Journal officiel) est obligatoire")
    if src.created_by == p.id and not p.is_director:
        raise HTTPException(403, "La vérification doit être faite par une autre personne que l'auteur de la saisie")
    src.verified_by, src.verified_at = p.id, now()
    audit(s, p.id, "legal.verified", f"legal:{src.id}", ip=client_ip(request))
    s.commit()
    return _out(src)
