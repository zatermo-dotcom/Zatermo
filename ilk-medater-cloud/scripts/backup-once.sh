#!/bin/sh
# Une sauvegarde complète. Utilisable seule : docker compose exec backup sh /scripts/backup-once.sh
set -eu
TS=$(date +%Y%m%d-%H%M%S)
OUT=/backups/$TS
mkdir -p "$OUT"
pg_dump --format=custom --no-owner --file="$OUT/ilk.dump"
tar -czf "$OUT/documents.tar.gz" -C /data documents
( cd "$OUT" && sha256sum ilk.dump documents.tar.gz > SHA256SUMS )
echo "$(date -Iseconds) sauvegarde OK : $OUT"
find /backups -mindepth 1 -maxdepth 1 -type d -mtime +"${BACKUP_RETENTION_DAYS:-30}" -exec rm -rf {} +
