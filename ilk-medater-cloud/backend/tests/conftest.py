"""Tests d'intégration contre un vrai PostgreSQL (aucune base simulée).

Variables : TEST_OWNER_DSN (propriétaire, crée la base de test) et TEST_APP_PASSWORD (rôle ilk_app existant).
Par défaut : postgresql://ilk:ilktest@localhost:5432 et ilk_app / apptest.
"""
import os
import uuid

import psycopg
import pyotp
import pytest

OWNER_BASE = os.environ.get("TEST_OWNER_DSN", "postgresql://ilk:ilktest@localhost:5432")
APP_PASSWORD = os.environ.get("TEST_APP_PASSWORD", "apptest")
DB_NAME = f"ilk_test_{uuid.uuid4().hex[:8]}"
HOSTPORT = OWNER_BASE.split("@", 1)[1]

os.environ.update({
    "SESSION_SECRET": "t" * 40,
    "MFA_ENCRYPTION_KEY": "m" * 40,
    "DATABASE_URL": f"postgresql+psycopg://ilk_app:{APP_PASSWORD}@{HOSTPORT}/{DB_NAME}",
    "MIGRATION_DATABASE_URL": f"{OWNER_BASE}/{DB_NAME}",
    "DOCUMENTS_DIR": f"/tmp/ilk-test-docs-{DB_NAME}",
    "OLLAMA_URL": "",
    "CLOUD_AI_PROVIDER": "",
    "RATE_LIMIT_PER_MINUTE": "100000",
    "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
})

DIRECTOR_EMAIL = "dg@ilk-medater.dz"
DIRECTOR_PASSWORD = "Directeur-2026!"
TOTP_SECRET = pyotp.random_base32()


@pytest.fixture(scope="session", autouse=True)
def database():
    with psycopg.connect(f"{OWNER_BASE}/postgres", autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{DB_NAME}"')
    from app.migrate import run
    run(os.environ["MIGRATION_DATABASE_URL"])
    from app.security import encrypt_secret, hasher
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"]) as c:
        uid = c.execute("""INSERT INTO users(email, full_name, password_hash, is_group_director, must_change_password, mfa_enabled, mfa_secret_enc)
                           VALUES (%s, 'Directeur Test', %s, true, false, true, %s) RETURNING id""",
                        (DIRECTOR_EMAIL, hasher.hash(DIRECTOR_PASSWORD), encrypt_secret(TOTP_SECRET))).fetchone()[0]
        c.execute("INSERT INTO ai_settings(user_id, local_enabled, cloud_enabled, updated_by) VALUES (%s, true, false, %s)", (uid, uid))
    yield
    from app.db import engine
    engine().dispose()
    with psycopg.connect(f"{OWNER_BASE}/postgres", autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)')


@pytest.fixture(autouse=True)
def _reset_limits():
    from app.security import limiter
    limiter.reset()


def make_client():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    c.headers["x-ilk-csrf"] = "1"
    return c


@pytest.fixture
def owner_db():
    with psycopg.connect(os.environ["MIGRATION_DATABASE_URL"], autocommit=True) as c:
        yield c


@pytest.fixture
def app_db():
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url, autocommit=True) as c:
        yield c


def director_totp() -> str:
    return pyotp.TOTP(TOTP_SECRET).now()


@pytest.fixture
def dg():
    c = make_client()
    r = c.post("/api/auth/login", json={"email": DIRECTOR_EMAIL, "password": DIRECTOR_PASSWORD})
    assert r.status_code == 200, r.text
    r = c.post("/api/auth/mfa/verify", json={"code": director_totp()})
    assert r.status_code == 200, r.text
    return c


def companies(dg):
    return {c["code"]: c["id"] for c in dg.get("/api/admin/catalog").json()["companies"]}


def new_user(dg, email=None, password="Temporaire-2026!", grants=(), ai=None, company="CONST"):
    """Crée un compte via la console DG, applique les autorisations, et renvoie un client connecté."""
    email = email or f"u{uuid.uuid4().hex[:8]}@ilk-medater.dz"
    r = dg.post("/api/admin/users", json={"email": email, "full_name": "Collaborateur Test", "temporary_password": password,
                                          "company_id": companies(dg)[company]})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    for g in grants:
        r = dg.post("/api/admin/grants", json={"user_id": uid, **g})
        assert r.status_code == 201, r.text
    if ai:
        assert dg.put(f"/api/admin/users/{uid}/ai", json=ai).status_code == 200
    c = make_client()
    assert c.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    new_pw = "Nouveau-Mot2passe!"
    r = c.post("/api/auth/password", json={"current_password": password, "new_password": new_pw})
    assert r.status_code == 200, r.text
    c.user_id = uid
    c.email = email
    c.password = new_pw
    return c
