# Test de restauration non destructif de la dernière sauvegarde (base temporaire supprimée à la fin).
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
docker compose exec backup sh /scripts/restore-test.sh
