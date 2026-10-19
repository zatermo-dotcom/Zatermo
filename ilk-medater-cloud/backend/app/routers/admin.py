"""Console du Directeur général : comptes, autorisations, IA, sessions et journal d'audit.

Toutes les routes exigent le Directeur général (contrôle applicatif) ; la base refuse en plus toute
autorisation dont l'auteur n'est pas le Directeur (trigger grants_director_only).
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..audit import audit
from ..authz import ACTIONS, MODULES, Principal, company_ids, org_units
from ..db import get_db
from ..deps import client_ip, director
from ..models import AiSettings, AuditEvent, Company, Document, Grant, Project, SessionRow, User
from ..security import hash_password, now

router = APIRouter(prefix="/admin", tags=["direction"])


class AccountIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    job_title: str = Field(default="", max_length=120)
    company_id: int = Field(description="Filiale de rattachement (obligatoire : un collaborateur appartient à une seule filiale)")
    org_unit_code: Optional[str] = None
    temporary_password: str = Field(min_length=12, max_length=256)


class AccountPatch(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    job_title: Optional[str] = Field(default=None, max_length=120)
    org_unit_code: Optional[str] = None
    company_id: Optional[int] = None
    enabled: Optional[bool] = None


class PasswordReset(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=256)


class GrantIn(BaseModel):
    user_id: int
    scope_type: Literal["company", "org_unit", "module", "project", "document"]
    scope_ref: str = Field(min_length=1, max_length=60)
    company_id: Optional[int] = None
    actions: list[Literal["view", "edit", "validate", "export"]] = Field(min_length=1)
    expires_at: Optional[datetime] = None
    note: str = Field(default="", max_length=300)

    @field_validator("actions")
    @classmethod
    def _dedupe(cls, v):
        return sorted(set(v), key=ACTIONS.index)


class GrantPatch(BaseModel):
    status: Optional[Literal["active", "suspended", "revoked"]] = None
    expires_at: Optional[datetime] = None
    clear_expiry: bool = False
    actions: Optional[list[Literal["view", "edit", "validate", "export"]]] = None


class AiIn(BaseModel):
    local_enabled: bool
    cloud_enabled: bool


def _user_out(u: User, grants: list[Grant], ai: AiSettings | None, sessions: int) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "job_title": u.job_title,
            "org_unit_code": u.org_unit_code, "company_id": u.company_id, "enabled": u.enabled, "is_group_director": u.is_group_director,
            "mfa_enabled": u.mfa_enabled, "must_change_password": u.must_change_password,
            "locked": bool(u.locked_until and u.locked_until > now()),
            "last_login_at": u.last_login_at, "active_sessions": sessions,
            "ai": {"local": bool(ai and ai.local_enabled), "cloud": bool(ai and ai.cloud_enabled)},
            "grants": [_grant_out(g) for g in grants]}


def _grant_out(g: Grant) -> dict:
    expired = bool(g.expires_at and g.expires_at <= now())
    return {"id": g.id, "user_id": g.user_id, "scope_type": g.scope_type, "scope_ref": g.scope_ref,
            "company_id": g.company_id, "actions": g.actions, "status": "expired" if expired and g.status == "active" else g.status,
            "expires_at": g.expires_at, "note": g.note, "granted_at": g.granted_at, "updated_at": g.updated_at}


@router.get("/users")
def list_users(p: Principal = Depends(director), s: Session = Depends(get_db)):
    users = s.scalars(select(User).order_by(User.is_group_director.desc(), User.full_name)).all()
    grants = s.scalars(select(Grant).where(Grant.status != "revoked").order_by(Grant.id)).all()
    ai = {a.user_id: a for a in s.scalars(select(AiSettings)).all()}
    sess = dict(s.execute(select(SessionRow.user_id, func.count()).where(
        SessionRow.revoked_at.is_(None), SessionRow.expires_at > now()).group_by(SessionRow.user_id)).all())
    return [_user_out(u, [g for g in grants if g.user_id == u.id], ai.get(u.id), sess.get(u.id, 0)) for u in users]


@router.post("/users", status_code=201)
def create_user(data: AccountIn, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    if s.scalar(select(User).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(409, "Un compte existe déjà avec cet email")
    _check_company(s, data.company_id)
    _check_unit(s, data.org_unit_code, data.company_id)
    try:
        ph = hash_password(data.temporary_password)
    except ValueError as e:
        raise HTTPException(422, str(e))
    u = User(email=data.email.lower(), full_name=data.full_name, job_title=data.job_title,
             org_unit_code=data.org_unit_code, company_id=data.company_id, password_hash=ph, enabled=True, must_change_password=True)
    s.add(u)
    s.flush()
    audit(s, p.id, "user.created", f"user:{u.id}", details={"email": u.email, "company_id": u.company_id, "rights": "aucun"}, ip=client_ip(request))
    s.commit()
    return {"id": u.id, "rights": "aucun droit métier tant que le Directeur n'en attribue pas"}


@router.patch("/users/{user_id}")
def patch_user(user_id: int, data: AccountPatch, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    u = s.get(User, user_id)
    if not u:
        raise HTTPException(404, "Compte introuvable")
    if u.is_group_director and data.enabled is False:
        raise HTTPException(422, "Le compte du Directeur général ne peut pas être désactivé depuis l'application")
    changes = data.model_dump(exclude_none=True)
    if u.is_group_director and ("company_id" in changes or "org_unit_code" in changes):
        raise HTTPException(422, "Le Directeur général n'est rattaché à aucune filiale : il voit les deux")
    if "company_id" in changes:
        _check_company(s, changes["company_id"])
        if s.scalar(select(func.count()).select_from(Grant).where(Grant.user_id == u.id, Grant.status != "revoked")):
            raise HTTPException(409, "Révoquer les autorisations du collaborateur avant de changer sa filiale de rattachement")
    if "org_unit_code" in changes or "company_id" in changes:
        _check_unit(s, changes.get("org_unit_code", u.org_unit_code), changes.get("company_id", u.company_id))
    for k, v in changes.items():
        setattr(u, k, v)
    if data.enabled is False:
        _revoke_sessions(s, u.id)
    audit(s, p.id, "user.updated", f"user:{u.id}", details=changes, ip=client_ip(request))
    s.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, data: PasswordReset, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    u = s.get(User, user_id)
    if not u or u.is_group_director:
        raise HTTPException(422, "Compte introuvable ou protégé (récupération du Directeur : procédure hors ligne)")
    try:
        u.password_hash = hash_password(data.temporary_password)
    except ValueError as e:
        raise HTTPException(422, str(e))
    u.must_change_password = True
    u.failed_logins = 0
    u.locked_until = None
    _revoke_sessions(s, u.id)
    audit(s, p.id, "user.password_reset", f"user:{u.id}", ip=client_ip(request))
    s.commit()
    return {"status": "ok"}


@router.post("/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id: int, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    n = _revoke_sessions(s, user_id)
    audit(s, p.id, "user.sessions_revoked", f"user:{user_id}", details={"count": n}, ip=client_ip(request))
    s.commit()
    return {"revoked": n}


def _check_company(s: Session, cid: int | None) -> None:
    if cid not in company_ids(s).values():
        raise HTTPException(422, "Filiale de rattachement inconnue")


def _check_unit(s: Session, code: str | None, cid: int | None) -> None:
    """Le département d'un collaborateur appartient à sa filiale (aucun service commun porteur de données)."""
    if not code:
        return
    unit = org_units(s).get(code)
    if not unit or not unit.active:
        raise HTTPException(422, "Département inconnu ou supprimé")
    if unit.company_code == "GROUP":
        if unit.code == "SHARED-EXEC" or unit.modules:
            raise HTTPException(422, "Ce service relève de la seule Direction générale")
        return
    if company_ids(s)[unit.company_code] != cid:
        raise HTTPException(422, "Filiales séparées : le département appartient à l'autre filiale")


def _revoke_sessions(s: Session, user_id: int) -> int:
    n = 0
    for row in s.scalars(select(SessionRow).where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))):
        row.revoked_at = now()
        n += 1
    return n


def _validate_scope(s: Session, g: GrantIn) -> int | None:
    """Vérifie le périmètre et renvoie la filiale concernée."""
    comps = company_ids(s)
    if g.scope_type == "company":
        cid = int(g.scope_ref) if g.scope_ref.isdigit() else comps.get(g.scope_ref)
        if cid not in comps.values():
            raise HTTPException(422, "Filiale inconnue")
        g.scope_ref = str(cid)
        return cid
    if g.scope_type == "module":
        if g.scope_ref not in MODULES:
            raise HTTPException(422, "Module inconnu")
        if g.company_id not in comps.values():
            raise HTTPException(422, "Préciser la filiale du module")
        return g.company_id
    if g.scope_type == "org_unit":
        unit = org_units(s).get(g.scope_ref)
        if not unit or not unit.active:
            raise HTTPException(422, "Département inconnu ou supprimé")
        if not unit.modules:
            raise HTTPException(422, "Ce service n'ouvre aucun module métier")
        if unit.company_code == "GROUP":
            raise HTTPException(422, "Les services de la Direction générale ne s'ouvrent pas par autorisation")
        return comps[unit.company_code]
    ref = int(g.scope_ref) if g.scope_ref.isdigit() else None
    obj = s.get(Project if g.scope_type == "project" else Document, ref) if ref else None
    if not obj:
        raise HTTPException(422, "Projet ou document introuvable")
    return obj.company_id


@router.post("/grants", status_code=201)
def create_grant(data: GrantIn, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    target = s.get(User, data.user_id)
    if not target:
        raise HTTPException(404, "Compte introuvable")
    if target.is_group_director:
        raise HTTPException(422, "Le Directeur général dispose déjà de tous les droits")
    if data.expires_at and data.expires_at <= now():
        raise HTTPException(422, "La date d'expiration doit être future")
    cid = _validate_scope(s, data)
    if target.company_id is None:
        raise HTTPException(422, "Rattacher d'abord ce collaborateur à une filiale")
    if cid != target.company_id:
        raise HTTPException(422, "Filiales séparées : ce collaborateur appartient à l'autre filiale. "
                                 "Seule la Direction générale accède aux informations des deux filiales.")
    g = Grant(user_id=data.user_id, company_id=cid, scope_type=data.scope_type, scope_ref=data.scope_ref,
              actions=list(data.actions), expires_at=data.expires_at, note=data.note, granted_by=p.id, changed_by=p.id)
    s.add(g)
    s.flush()
    audit(s, p.id, "grant.created", f"grant:{g.id}", company_id=cid,
          details={"user": data.user_id, "scope": f"{data.scope_type}:{data.scope_ref}", "actions": g.actions,
                   "expires_at": data.expires_at}, ip=client_ip(request))
    s.commit()
    return _grant_out(g)


@router.patch("/grants/{grant_id}")
def patch_grant(grant_id: int, data: GrantPatch, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    g = s.get(Grant, grant_id)
    if not g:
        raise HTTPException(404, "Autorisation introuvable")
    if g.status == "revoked":
        raise HTTPException(409, "Une autorisation révoquée est définitive")
    before = _grant_out(g)
    if data.status:
        g.status = data.status
        if data.status == "revoked":
            g.revoked_at = now()
    if data.clear_expiry:
        g.expires_at = None
    elif data.expires_at:
        if data.expires_at <= now():
            raise HTTPException(422, "La date d'expiration doit être future")
        g.expires_at = data.expires_at
    if data.actions:
        g.actions = sorted(set(data.actions), key=ACTIONS.index)
    g.changed_by = p.id
    audit(s, p.id, f"grant.{data.status or 'updated'}", f"grant:{g.id}", company_id=g.company_id,
          details={"before": before, "changes": data.model_dump(exclude_none=True)}, ip=client_ip(request))
    s.commit()
    return _grant_out(g)


@router.put("/users/{user_id}/ai")
def set_ai(user_id: int, data: AiIn, request: Request, p: Principal = Depends(director), s: Session = Depends(get_db)):
    if not s.get(User, user_id):
        raise HTTPException(404, "Compte introuvable")
    row = s.get(AiSettings, user_id)
    if not row:
        row = AiSettings(user_id=user_id, updated_by=p.id)
        s.add(row)
    row.local_enabled = data.local_enabled
    row.cloud_enabled = data.cloud_enabled
    row.updated_by = p.id
    audit(s, p.id, "ai.settings", f"user:{user_id}", details=data.model_dump(), ip=client_ip(request))
    s.commit()
    return {"status": "ok"}


@router.get("/audit")
def audit_log(p: Principal = Depends(director), s: Session = Depends(get_db),
              limit: int = Query(200, le=1000), before_id: Optional[int] = None, action: Optional[str] = None,
              actor_id: Optional[int] = None):
    q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if before_id:
        q = q.where(AuditEvent.id < before_id)
    if action:
        q = q.where(AuditEvent.action.startswith(action))
    if actor_id:
        q = q.where(AuditEvent.actor_id == actor_id)
    return [{"id": a.id, "at": a.at, "actor_id": a.actor_id, "action": a.action, "resource": a.resource,
             "company_id": a.company_id, "details": a.details, "ip": a.ip, "hash": a.hash[:16]} for a in s.scalars(q)]


@router.get("/audit/verify")
def audit_verify(p: Principal = Depends(director), s: Session = Depends(get_db)):
    broken = s.execute(text("SELECT broken_id, reason FROM audit_verify()")).first()
    total = s.scalar(select(func.count()).select_from(AuditEvent))
    return {"intact": broken is None, "events": total,
            "broken_id": broken[0] if broken else None, "reason": broken[1] if broken else None}


@router.get("/catalog")
def catalog(p: Principal = Depends(director), s: Session = Depends(get_db)):
    """Listes utilisées par la console pour construire les autorisations."""
    comps = s.scalars(select(Company).order_by(Company.id)).all()
    projects = s.scalars(select(Project).order_by(Project.company_id, Project.code)).all()
    return {"companies": [{"id": c.id, "code": c.code, "name": c.name} for c in comps],
            "modules": [{"code": k, "name": v} for k, v in MODULES.items()],
            "actions": list(ACTIONS),
            "org_units": [{"code": u.code, "name": u.name, "company_code": u.company_code, "kind": u.kind,
                           "modules": u.modules} for u in sorted(org_units(s).values(), key=lambda u: u.sort) if u.modules],
            "projects": [{"id": x.id, "code": x.code, "name": x.name, "company_id": x.company_id} for x in projects]}
