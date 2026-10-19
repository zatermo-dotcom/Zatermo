"""Commandes d'administration hors ligne (exécutées sur le serveur, avec le rôle propriétaire de la base).

  python -m app.cli create-director --email dg@exemple.dz --name "Nom Prénom"
        Crée l'unique compte Directeur général, enrôle la MFA et affiche les codes de récupération (une seule fois).
  python -m app.cli reset-director-mfa
        Récupération du compte de direction (perte du téléphone) : nouveau secret TOTP + nouveaux codes,
        toutes les sessions révoquées. Nécessite l'accès physique/administrateur au serveur.
  python -m app.cli reset-director-password
        Nouveau mot de passe temporaire pour le Directeur (changement imposé à la connexion suivante).
  python -m app.cli verify-audit
        Vérifie l'intégrité du chaînage du journal d'audit.

Ces opérations sont journalisées. Le mot de passe est saisi de façon masquée, jamais passé en argument.
"""
import argparse
import getpass
import json
import sys

import psycopg

from .config import get_settings
from .security import (encrypt_secret, hash_password, hasher, new_recovery_codes, new_totp_secret, normalize_recovery,
                       totp_uri)


def _conn():
    url = get_settings().migration_database_url
    if not url:
        sys.exit("MIGRATION_DATABASE_URL non défini")
    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def _ask_password() -> str:
    pw = getpass.getpass("Mot de passe (12 caractères min.) : ")
    if pw != getpass.getpass("Confirmer : "):
        sys.exit("Les mots de passe diffèrent")
    try:
        return hash_password(pw)
    except ValueError as e:
        sys.exit(str(e))


def _audit(c, actor, action, details):
    c.execute("SELECT audit_append(%s, %s, %s, NULL, %s::jsonb, 'cli')", (actor, action, f"user:{actor}", json.dumps(details)))


def _enrol(c, user_id: int, email: str) -> None:
    secret = new_totp_secret()
    codes = new_recovery_codes()
    c.execute("UPDATE users SET mfa_secret_enc=%s, mfa_enabled=true WHERE id=%s", (encrypt_secret(secret), user_id))
    c.execute("UPDATE recovery_codes SET used_at=now() WHERE user_id=%s AND used_at IS NULL", (user_id,))
    for code in codes:
        c.execute("INSERT INTO recovery_codes(user_id, code_hash) VALUES (%s, %s)", (user_id, hasher.hash(normalize_recovery(code))))
    c.execute("UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (user_id,))
    print("\n=== MFA — à enregistrer dans l'application d'authentification (Google Authenticator, Aegis…) ===")
    print(f"Clé secrète : {secret}")
    print(f"URI         : {totp_uri(secret, email)}")
    print("\n=== Codes de récupération (usage unique) — à imprimer et conserver sous enveloppe scellée ===")
    for code in codes:
        print("  ", code)
    print("Ces informations ne seront plus jamais affichées.\n")


def create_director(email: str, name: str) -> None:
    with _conn() as c:
        if c.execute("SELECT 1 FROM users WHERE is_group_director").fetchone():
            sys.exit("Un Directeur général existe déjà. Utiliser les commandes reset-*.")
        ph = _ask_password()
        uid = c.execute("""INSERT INTO users(email, full_name, job_title, org_unit_code, password_hash, is_group_director,
                           must_change_password, enabled) VALUES (%s,%s,'Directeur général','SHARED-EXEC',%s,true,false,true)
                           RETURNING id""", (email.lower(), name, ph)).fetchone()[0]
        c.execute("INSERT INTO ai_settings(user_id, local_enabled, cloud_enabled, updated_by) VALUES (%s, true, false, %s)", (uid, uid))
        _enrol(c, uid, email)
        _audit(c, uid, "director.created", {"email": email.lower()})
    print(f"Compte Directeur général créé (id {uid}).")


def _director(c):
    row = c.execute("SELECT id, email FROM users WHERE is_group_director").fetchone()
    if not row:
        sys.exit("Aucun Directeur général. Utiliser create-director.")
    return row


def reset_director_mfa() -> None:
    with _conn() as c:
        uid, email = _director(c)
        if input(f"Réinitialiser la MFA de {email} ? Taper OUI : ") != "OUI":
            sys.exit("Annulé")
        _enrol(c, uid, email)
        _audit(c, uid, "director.mfa_reset", {"via": "cli"})


def reset_director_password() -> None:
    with _conn() as c:
        uid, email = _director(c)
        ph = _ask_password()
        c.execute("UPDATE users SET password_hash=%s, must_change_password=true, failed_logins=0, locked_until=NULL WHERE id=%s", (ph, uid))
        c.execute("UPDATE sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", (uid,))
        _audit(c, uid, "director.password_reset", {"via": "cli"})
    print("Mot de passe réinitialisé ; changement imposé à la prochaine connexion.")


def verify_audit() -> None:
    with _conn() as c:
        broken = c.execute("SELECT broken_id, reason FROM audit_verify()").fetchone()
        n = c.execute("SELECT count(*) FROM audit_events").fetchone()[0]
    if broken:
        sys.exit(f"JOURNAL ALTÉRÉ : événement {broken[0]} ({broken[1]}) sur {n}")
    print(f"Journal intègre : {n} événements.")


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cd = sub.add_parser("create-director")
    cd.add_argument("--email", required=True)
    cd.add_argument("--name", required=True)
    sub.add_parser("reset-director-mfa")
    sub.add_parser("reset-director-password")
    sub.add_parser("verify-audit")
    a = ap.parse_args()
    {"create-director": lambda: create_director(a.email, a.name), "reset-director-mfa": reset_director_mfa,
     "reset-director-password": reset_director_password, "verify-audit": verify_audit}[a.cmd]()


if __name__ == "__main__":
    main()
