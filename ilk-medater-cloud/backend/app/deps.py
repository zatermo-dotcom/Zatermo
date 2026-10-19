"""Dépendances FastAPI : session courante, MFA, changement de mot de passe obligatoire, rôle Directeur."""
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .authz import Principal, load_principal
from .config import get_settings
from .db import get_db
from .models import SessionRow, User
from .security import SESSION_COOKIE, now, token_hash


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "-"


def _session(request: Request, s: Session) -> tuple[SessionRow, User]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Connexion requise")
    row = s.scalar(select(SessionRow).where(SessionRow.token_hash == token_hash(token)))
    t = now()
    cfg = get_settings()
    if not row or row.revoked_at or row.expires_at <= t or row.last_seen_at + timedelta(minutes=cfg.session_idle_minutes) <= t:
        raise HTTPException(401, "Session expirée, reconnectez-vous")
    user = s.get(User, row.user_id)
    if not user or not user.enabled:
        raise HTTPException(401, "Compte désactivé")
    if (t - row.last_seen_at).total_seconds() > 60:
        row.last_seen_at = t
        s.commit()
    return row, user


def mfa_required(user: User) -> bool:
    return user.is_group_director or user.mfa_enabled or get_settings().mfa_required_for_all


def pending_session(request: Request, s: Session = Depends(get_db)) -> tuple[SessionRow, User]:
    """Session éventuellement incomplète (MFA en attente) : réservé aux routes /auth/*."""
    return _session(request, s)


def current(request: Request, s: Session = Depends(get_db)) -> Principal:
    row, user = _session(request, s)
    if mfa_required(user) and not row.mfa_verified:
        raise HTTPException(401, "Vérification MFA requise")
    if user.must_change_password:
        raise HTTPException(403, "Changement de mot de passe obligatoire avant toute action")
    return load_principal(s, user, row.id)


def director(p: Principal = Depends(current)) -> Principal:
    if not p.is_director:
        raise HTTPException(403, "Réservé au Directeur général du groupe")
    return p
