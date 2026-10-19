# Crée l'unique compte Directeur général (mot de passe saisi de façon masquée, MFA + codes de récupération affichés une fois).
param([Parameter(Mandatory=$true)][string]$Email, [Parameter(Mandatory=$true)][string]$Nom)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))
docker compose run --rm -it migrate python -m app.cli create-director --email $Email --name $Nom
