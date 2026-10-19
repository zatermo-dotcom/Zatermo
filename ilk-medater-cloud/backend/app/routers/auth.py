"""Authentification : mot de passe + MFA TOTP, sessions serveur en cookie HttpOnly, verrouillage anti force brute."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import audit
from ..authz import Principal
from ..config import get_settings
from ..db import get_db
from ..deps import client_ip, current, mfa_required, pending_session
from ..models import RecoveryCode, SessionRow, User
from ..security import (SESSION_COOKIE, decrypt_secret, encrypt_secret, hash_password, hasher, limiter,
                        new_recovery_codes, new_session_token, new_totp_secret, normalize_recovery, now,
                        session_expiry, totp_uri, verify_password, verify_totp)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class MfaIn(BaseModel):
    code: str = Field(default="", max_length=10)
    recovery_code: str = Field(default="", max_length=40)


class PasswordIn(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


def _set_cookie(resp: Response, token: str) -> None:
    cfg = get_settings()
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, secure=cfg.cookie_secure, samesite="strict",
                    max_age=cfg.session_absolute_hours * 3600, path="/")


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, s: Session = Depends(get_db)):
    ip = client_ip(request)
    cfg = get_settings()
    if not limiter.allow(f"login:{ip}", cfg.login_rate_limit_per_minute):
        raise HTTPException(429, "Trop de tentatives, réessayez dans une minute")
    user = s.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    t = now()
    if user and user.locked_until and user.locked_until > t:
        audit(s, user.id, "auth.login_blocked", f"user:{user.id}", ip=ip)
        s.commit()
        raise HTTPException(423, "Compte temporairement verrouillé après plusieurs échecs")
    ok, upgraded_hash = False, None
    if user:
        try:
            ok, upgraded_hash = hasher.verify_and_update(data.password, user.password_hash)
        except Exception:
            ok = False
    else:
        verify_password(data.password, None)  # temps de réponse constant
    if not user or not ok or not user.enabled:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= cfg.max_failed_logins:
                user.locked_until = t + timedelta(minutes=cfg.lockout_minutes)
                user.failed_logins = 0
            audit(s, user.id, "auth.login_failed", f"user:{user.id}", ip=ip)
            s.commit()
        raise HTTPException(401, "Identifiants invalides")
    if upgraded_hash:  # paramètres Argon2 renforcés depuis le dernier hachage
        user.password_hash = upgraded_hash
    user.failed_logins = 0
    user.locked_until = None
    token, th = new_session_token()
    needs_mfa = mfa_required(user)
    s.add(SessionRow(user_id=user.id, token_hash=th, mfa_verified=not needs_mfa, expires_at=session_expiry(),
                     ip=ip, user_agent=(request.headers.get("user-agent") or "")[:300]))
    if not needs_mfa:
        user.last_login_at = t
    audit(s, user.id, "auth.password_ok" if needs_mfa else "auth.login", f"user:{user.id}", ip=ip)
    s.commit()
    _set_cookie(response, token)
    return {"mfa_required": needs_mfa and user.mfa_enabled,
            "mfa_setup_required": needs_mfa and not user.mfa_enabled,
            "must_change_password": user.must_change_password}


@router.post("/mfa/verify")
def mfa_verify(data: MfaIn, request: Request, s: Session = Depends(get_db), ctx=Depends(pending_session)):
    row, user = ctx
    ip = client_ip(request)
    if not limiter.allow(f"mfa:{row.id}", 5):
        raise HTTPException(429, "Trop de tentatives MFA")
    if not user.mfa_enabled or not user.mfa_secret_enc:
        raise HTTPException(409, "MFA non configurée pour ce compte")
    ok = False
    method = "totp"
    if data.code:
        ok = verify_totp(decrypt_secret(user.mfa_secret_enc), data.code)
    elif data.recovery_code:
        method = "recovery_code"
        code = normalize_recovery(data.recovery_code)
        for rc in s.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))):
            if verify_password(code, rc.code_hash):
                rc.used_at = now()
                ok = True
                break
    if not ok:
        audit(s, user.id, "auth.mfa_failed", f"user:{user.id}", ip=ip)
        s.commit()
        raise HTTPException(401, "Code invalide")
    row.mfa_verified = True
    user.last_login_at = now()
    audit(s, user.id, "auth.login", f"user:{user.id}", details={"mfa": method}, ip=ip)
    s.commit()
    remaining = s.scalar(select(func.count()).select_from(RecoveryCode).where(
        RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)))
    return {"status": "ok", "recovery_codes_remaining": remaining, "must_change_password": user.must_change_password}


@router.post("/mfa/setup")
def mfa_setup(request: Request, s: Session = Depends(get_db), ctx=Depends(pending_session)):
    """Démarre l'enrôlement TOTP d'un compte qui n'a pas encore de MFA (le Directeur est enrôlé par la CLI)."""
    row, user = ctx
    if user.mfa_enabled:
        raise HTTPException(409, "MFA déjà active ; la réinitialisation passe par la procédure de récupération")
    secret = new_totp_secret()
    user.mfa_secret_enc = encrypt_secret(secret)
    s.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, user.email)}


@router.post("/mfa/confirm")
def mfa_confirm(data: MfaIn, request: Request, s: Session = Depends(get_db), ctx=Depends(pending_session)):
    row, user = ctx
    if user.mfa_enabled or not user.mfa_secret_enc:
        raise HTTPException(409, "Aucun enrôlement MFA en cours")
    if not verify_totp(decrypt_secret(user.mfa_secret_enc), data.code):
        raise HTTPException(401, "Code invalide")
    user.mfa_enabled = True
    row.mfa_verified = True
    codes = new_recovery_codes()
    for c in codes:
        s.add(RecoveryCode(user_id=user.id, code_hash=hasher.hash(normalize_recovery(c))))
    audit(s, user.id, "auth.mfa_enrolled", f"user:{user.id}", ip=client_ip(request))
    s.commit()
    return {"status": "ok", "recovery_codes": codes}


@router.post("/password")
def change_password(data: PasswordIn, request: Request, s: Session = Depends(get_db), ctx=Depends(pending_session)):
    row, user = ctx
    if mfa_required(user) and not row.mfa_verified:
        raise HTTPException(401, "Vérification MFA requise")
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(401, "Mot de passe actuel incorrect")
    if data.new_password == data.current_password:
        raise HTTPException(422, "Le nouveau mot de passe doit être différent")
    try:
        user.password_hash = hash_password(data.new_password)
    except ValueError as e:
        raise HTTPException(422, str(e))
    user.must_change_password = False
    user.password_changed_at = now()
    # Révoque les autres sessions du compte.
    for other in s.scalars(select(SessionRow).where(SessionRow.user_id == user.id, SessionRow.id != row.id,
                                                    SessionRow.revoked_at.is_(None))):
        other.revoked_at = now()
    audit(s, user.id, "auth.password_changed", f"user:{user.id}", ip=client_ip(request))
    s.commit()
    return {"status": "ok"}


@router.post("/logout")
def logout(response: Response, request: Request, s: Session = Depends(get_db), ctx=Depends(pending_session)):
    row, user = ctx
    row.revoked_at = now()
    audit(s, user.id, "auth.logout", f"user:{user.id}", ip=client_ip(request))
    s.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "ok"}


@router.get("/me")
def me(p: Principal = Depends(current)):
    u = p.user
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "job_title": u.job_title,
            "org_unit_code": u.org_unit_code, "company_id": u.company_id, "is_group_director": u.is_group_director,
            "mfa_enabled": u.mfa_enabled, **p.capabilities()}
