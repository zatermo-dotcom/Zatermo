#!/bin/sh
# Test de restauration NON destructif : restaure la dernière sauvegarde dans une base temporaire,
# vérifie les empreintes, le nombre de tables et l'intégrité du journal d'audit, puis supprime la base temporaire.
# Usage : docker compose exec backup sh /scripts/restore-test.sh [dossier]
set -eu
DIR=${1:-$(ls -1d /backups/*/ 2>/dev/null | sort | tail -n 1)}
[ -n "$DIR" ] || { echo "Aucune sauvegarde trouvée"; exit 1; }
cd "$DIR" && sha256sum -c SHA256SUMS
TMP=ilk_restore_test_$(date +%s)
createdb "$TMP"
trap 'dropdb --if-exists "$TMP"' EXIT
pg_restore --no-owner --exit-on-error --dbname="$TMP" ilk.dump
TABLES=$(psql -tA -d "$TMP" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
BROKEN=$(psql -tA -d "$TMP" -c "SELECT count(*) FROM audit_verify()")
EVENTS=$(psql -tA -d "$TMP" -c "SELECT count(*) FROM audit_events")
echo "Tables restaurées : $TABLES ; événements d'audit : $EVENTS ; ruptures de chaînage : $BROKEN"
[ "$TABLES" -ge 30 ] && [ "$BROKEN" -eq 0 ] && echo "RESTAURATION VALIDÉE" || { echo "RESTAURATION EN ÉCHEC"; exit 1; }
