"""Applique les migrations SQL versionnées (migrations/NNN_*.sql) avec le rôle propriétaire.

Usage : python -m app.migrate            (applique les migrations manquantes)
        python -m app.migrate --status   (affiche l'état)
Chaque fichier est appliqué dans une transaction ; sa somme SHA-256 est enregistrée et vérifiée ensuite,
pour détecter toute modification d'une migration déjà appliquée.
"""
import hashlib
import sys
from pathlib import Path

import psycopg

from .config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _dsn(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))


def run(url: str | None = None, status_only: bool = False) -> list[str]:
    url = url or get_settings().migration_database_url
    if not url:
        raise SystemExit("MIGRATION_DATABASE_URL non défini")
    applied_now: list[str] = []
    with psycopg.connect(_dsn(url), autocommit=False) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())""")
        conn.commit()
        done = dict(conn.execute("SELECT version, checksum FROM schema_migrations").fetchall())
        for f in migration_files():
            sql = f.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if f.name in done:
                if done[f.name] != checksum:
                    raise SystemExit(f"La migration {f.name} a été modifiée après application (somme différente).")
                continue
            if status_only:
                print(f"en attente : {f.name}")
                continue
            with conn.transaction():
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations(version, checksum) VALUES (%s, %s)", (f.name, checksum))
            applied_now.append(f.name)
            print(f"appliquée : {f.name}")
    if not applied_now and not status_only:
        print("Base à jour.")
    return applied_now


if __name__ == "__main__":
    run(status_only="--status" in sys.argv)
