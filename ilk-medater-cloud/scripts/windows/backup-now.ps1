# Lance immédiatement une sauvegarde (base + documents) dans .\backups
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
docker compose exec backup sh /scripts/backup-once.sh
