#!/bin/sh
# Sauvegarde périodique : base (pg_dump format custom) + documents, avec empreintes SHA-256 et rétention.
set -u
INTERVAL=$(( ${BACKUP_INTERVAL_HOURS:-24} * 3600 ))
while true; do
  /bin/sh /scripts/backup-once.sh || echo "$(date -Iseconds) ÉCHEC de la sauvegarde" >&2
  sleep "$INTERVAL"
done
