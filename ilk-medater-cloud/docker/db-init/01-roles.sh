#!/bin/sh
# Exécuté une seule fois, à la création du volume PostgreSQL.
# Crée le rôle applicatif restreint ilk_app (les droits fins sont posés par la migration 003).
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE ilk_app LOGIN PASSWORD '${APP_DB_PASSWORD}';
GRANT CONNECT ON DATABASE "${POSTGRES_DB}" TO ilk_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
