"""Authentification, MFA, sessions, journal d'audit et règles imposées par la base."""
import psycopg
import pytest
from sqlalchemy import inspect as sa_inspect

from app import models
from tests.conftest import DIRECTOR_EMAIL, DIRECTOR_PASSWORD, companies, director_totp, make_client, new_user


def test_orm_matches_migrated_schema(owner_db):
    cols = {}
    for table, col in owner_db.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public'"):
        cols.setdefault(table, set()).add(col)
    for mapper in models.Base.registry.mappers:
        t = mapper.local_table
        missing = {c.name for c in t.columns} - cols.get(t.name, set())
        assert not missing, f"{t.name}: colonnes ORM absentes en base {missing}"


def test_health():
    assert make_client().get("/api/health").json()["status"] == "ok"


def test_director_needs_mfa():
    c = make_client()
    r = c.post("/api/auth/login", json={"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD})
    assert r.status_code == 200 and r.json()["mfa_required"] is True
    assert c.get("/api/auth/me").status_code == 401           # session incomplète
    assert c.post("/api/auth/mfa/verify", json={"code": "000000"}).status_code == 401
    assert c.post("/api/auth/mfa/verify", json={"code": director_totp()}).status_code == 200
    me = c.get("/api/auth/me").json()
    assert me["is_group_director"] is True and me["modules"]["finance"]["all_companies"] is True


def test_csrf_header_required():
    c = make_client()
    del c.headers["x-ilk-csrf"]
    assert c.post("/api/auth/login", json={"email": DIRECTOR_EMAIL, "password": "x"}).status_code == 403


def test_bad_password_and_lockout(dg):
    u = new_user(dg)
    c = make_client()
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": u.email, "password": "mauvais-Mot-2026"}).status_code == 401
    r = c.post("/api/auth/login", json={"email": u.email, "password": u.password})
    assert r.status_code == 423  # verrouillé malgré le bon mot de passe
    assert dg.post(f"/api/admin/users/{u.user_id}/reset-password", json={"temporary_password": "Reinitialise-2026!"}).status_code == 200
    assert c.post("/api/auth/login", json={"email": u.email, "password": "Reinitialise-2026!"}).status_code == 200


def test_unknown_email_same_error():
    r = make_client().post("/api/auth/login", json={"email": "inconnu@x.dz", "password": "Quelconque-2026"})
    assert r.status_code == 401 and r.json()["detail"] == "Identifiants invalides"


def test_must_change_password_blocks_business_calls(dg):
    dg.post("/api/admin/users", json={"email": "mcp@ilk-medater.dz", "full_name": "A B", "temporary_password": "Temporaire-2026!",
                                       "company_id": companies(dg)["CONST"]})
    c = make_client()
    r = c.post("/api/auth/login", json={"email": "mcp@ilk-medater.dz", "password": "Temporaire-2026!"})
    assert r.json()["must_change_password"] is True
    assert c.get("/api/projects").status_code == 403
    assert c.post("/api/auth/password", json={"current_password": "Temporaire-2026!", "new_password": "faible"}).status_code == 422
    assert c.post("/api/auth/password", json={"current_password": "Temporaire-2026!", "new_password": "Solide-Passe-2026"}).status_code == 200
    assert c.get("/api/projects").status_code == 200


def test_logout_revokes_session(dg):
    u = new_user(dg)
    assert u.get("/api/auth/me").status_code == 200
    assert u.post("/api/auth/logout").status_code == 200
    assert u.get("/api/auth/me").status_code == 401


def test_disabling_user_kills_sessions(dg):
    u = new_user(dg)
    assert dg.patch(f"/api/admin/users/{u.user_id}", json={"enabled": False}).status_code == 200
    assert u.get("/api/auth/me").status_code == 401


def test_user_mfa_enrolment(dg):
    import pyotp
    u = new_user(dg)
    secret = u.post("/api/auth/mfa/setup").json()["secret"]
    r = u.post("/api/auth/mfa/confirm", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200 and len(r.json()["recovery_codes"]) == 10
    code = r.json()["recovery_codes"][0]
    c = make_client()
    assert c.post("/api/auth/login", json={"email": u.email, "password": u.password}).json()["mfa_required"] is True
    assert c.post("/api/auth/mfa/verify", json={"recovery_code": code}).status_code == 200
    c2 = make_client()
    c2.post("/api/auth/login", json={"email": u.email, "password": u.password})
    assert c2.post("/api/auth/mfa/verify", json={"recovery_code": code}).status_code == 401  # usage unique


def test_audit_chain_and_immutability(dg, app_db, owner_db):
    new_user(dg)
    v = dg.get("/api/admin/audit/verify").json()
    assert v["intact"] is True and v["events"] > 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_db.execute("UPDATE audit_events SET action='x'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_db.execute("DELETE FROM audit_events")
    with pytest.raises(psycopg.errors.RaiseException):
        owner_db.execute("UPDATE audit_events SET action='falsifie' WHERE id = (SELECT min(id) FROM audit_events)")
    actions = [e["action"] for e in dg.get("/api/admin/audit?limit=50").json()]
    assert "user.created" in actions and "auth.login" in actions


def test_app_role_cannot_create_director_or_grant(app_db):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_db.execute("INSERT INTO users(email, password_hash, is_group_director) VALUES ('x@y.z','h',true)")
    uid = app_db.execute("INSERT INTO users(email, password_hash) VALUES ('plain@y.z','h') RETURNING id").fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException, match="Directeur"):
        app_db.execute("INSERT INTO grants(user_id, company_id, scope_type, scope_ref, actions, granted_by, changed_by) "
                       "VALUES (%s, 1, 'company', '1', '{view}', %s, %s)", (uid, uid, uid))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_db.execute("DELETE FROM projects")


def test_only_director_reaches_console(dg):
    u = new_user(dg)
    for path in ("/api/admin/users", "/api/admin/audit", "/api/admin/catalog"):
        assert u.get(path).status_code == 403
    assert u.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "company", "scope_ref": "CONST",
                                             "actions": ["view"]}).status_code == 403
    assert u.put(f"/api/admin/users/{u.user_id}/ai", json={"local_enabled": True, "cloud_enabled": True}).status_code == 403
