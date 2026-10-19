"""Directives de la Direction générale, suivies projet par projet.

* Seule la Direction générale émet, clôture, annule ou rouvre une directive (contrôle API + trigger en base).
* Les intervenants du projet (droit « modifier » sur le projet) en accusent réception et rendent compte :
  accusée → en cours → réalisée, avec une note obligatoire à chaque étape.
* Chacun ne voit que les directives des projets de sa filiale qui lui sont ouverts.
"""
from datetime import date
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..authz import Principal
from ..crud import row_dict
from ..db import get_db
from ..deps import client_ip, current
from ..models import Directive, DirectiveUpdate, Project, User
from ..security import now

router = APIRouter(prefix="/directives", tags=["directives"])

TEAM_STATUSES = {"accusee", "en_cours", "realisee"}
DIRECTOR_STATUSES = {"cloturee", "annulee", "en_cours"}


class DirectiveIn(BaseModel):
    model_config = {"extra": "forbid"}
    project_id: int
    title: Annotated[str, Field(min_length=3, max_length=200)]
    instructions: Annotated[str, Field(min_length=3, max_length=8000)]
    priority: Literal["normale", "haute", "urgente"] = "normale"
    due_date: Optional[date] = None


class UpdateIn(BaseModel):
    model_config = {"extra": "forbid"}
    note: Annotated[str, Field(min_length=2, max_length=4000)]
    new_status: Optional[Literal["accusee", "en_cours", "realisee", "cloturee", "annulee"]] = None


def _out(s: Session, d: Directive, with_updates: bool = False) -> dict:
    out = row_dict(d)
    proj = s.get(Project, d.project_id)
    out["project"] = {"id": proj.id, "code": proj.code, "name": proj.name}
    out["overdue"] = bool(d.due_date and d.due_date < date.today() and d.status not in ("realisee", "cloturee", "annulee"))
    if with_updates:
        names = {}
        rows = s.scalars(select(DirectiveUpdate).where(DirectiveUpdate.directive_id == d.id).order_by(DirectiveUpdate.id)).all()
        for r in rows:
            if r.author_id not in names:
                u = s.get(User, r.author_id)
                names[r.author_id] = (u.full_name or u.email) + (" (Direction générale)" if u.is_group_director else "")
        out["updates"] = [{**row_dict(r), "author": names[r.author_id]} for r in rows]
    return out


@router.get("")
def list_directives(project_id: Optional[int] = None, company_id: Optional[int] = None, status: Optional[str] = None,
                    p: Principal = Depends(current), s: Session = Depends(get_db)):
    q = select(Directive).where(p.scope_clause(Directive, "projects")).order_by(Directive.due_date.nulls_last(), Directive.id.desc())
    if project_id:
        q = q.where(Directive.project_id == project_id)
    if company_id:
        q = q.where(Directive.company_id == company_id)
    if status:
        q = q.where(Directive.status == status)
    return [_out(s, d) for d in s.scalars(q.limit(500))]


@router.get("/{did}")
def get_directive(did: int, p: Principal = Depends(current), s: Session = Depends(get_db)):
    d = s.get(Directive, did)
    if not d:
        raise HTTPException(404, "Directive introuvable")
    p.require("projects", "view", d.company_id, d.project_id)
    return _out(s, d, with_updates=True)


@router.post("", status_code=201)
def issue(data: DirectiveIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    if not p.is_director:
        raise HTTPException(403, "Seule la Direction générale émet des directives")
    proj = s.get(Project, data.project_id)
    if not proj:
        raise HTTPException(404, "Projet introuvable")
    d = Directive(**data.model_dump(), company_id=proj.company_id, issued_by=p.id)
    s.add(d)
    s.flush()
    audit(s, p.id, "directive.issued", f"directive:{d.id}", company_id=proj.company_id,
          details={"project": proj.code, "priority": d.priority, "due_date": d.due_date}, ip=client_ip(request))
    s.commit()
    return _out(s, d, with_updates=True)


@router.post("/{did}/updates", status_code=201)
def follow_up(did: int, data: UpdateIn, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    d = s.scalar(select(Directive).where(Directive.id == did).with_for_update())
    if not d:
        raise HTTPException(404, "Directive introuvable")
    if p.is_director:
        allowed = DIRECTOR_STATUSES | TEAM_STATUSES
    else:
        p.require("projects", "edit", d.company_id, d.project_id)
        allowed = TEAM_STATUSES
        if d.status in ("cloturee", "annulee"):
            raise HTTPException(409, "Directive clôturée ou annulée par la Direction générale")
    if data.new_status:
        if data.new_status not in allowed:
            raise HTTPException(403, "Seule la Direction générale clôture, annule ou rouvre une directive")
        if not p.is_director and data.new_status == "accusee" and d.status != "emise":
            raise HTTPException(409, "Directive déjà prise en compte")
        d.status = data.new_status
        if data.new_status in ("cloturee", "annulee"):
            d.closed_by, d.closed_at = p.id, now()
        elif p.is_director and d.closed_by:
            d.closed_by = p.id  # réouverture par la Direction générale
    s.add(DirectiveUpdate(directive_id=d.id, company_id=d.company_id, author_id=p.id, note=data.note, new_status=data.new_status))
    audit(s, p.id, f"directive.{data.new_status or 'note'}", f"directive:{d.id}", company_id=d.company_id, ip=client_ip(request))
    s.commit()
    return _out(s, d, with_updates=True)
