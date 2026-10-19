# Génère un fichier .env avec des secrets aléatoires forts (à lancer une seule fois, depuis le dossier du projet).
# Usage : powershell -ExecutionPolicy Bypass -File scripts\windows\init-secrets.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) { Write-Error ".env existe déjà : supprimez-le volontairement si vous voulez le régénérer (les données existantes deviendraient inaccessibles)." }

function New-Secret([int]$bytes) {
  $b = New-Object byte[] $bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
  return ([Convert]::ToBase64String($b) -replace '[+/=]', 'x')
}
$content = Get-Content (Join-Path $root ".env.example") -Raw
$content = $content -replace 'POSTGRES_PASSWORD=A_GENERER', ("POSTGRES_PASSWORD=" + (New-Secret 24))
$content = $content -replace 'APP_DB_PASSWORD=A_GENERER', ("APP_DB_PASSWORD=" + (New-Secret 24))
$content = $content -replace 'SESSION_SECRET=A_GENERER_64_CARACTERES', ("SESSION_SECRET=" + (New-Secret 48))
$content = $content -replace 'MFA_ENCRYPTION_KEY=A_GENERER_64_CARACTERES', ("MFA_ENCRYPTION_KEY=" + (New-Secret 48))
Set-Content -Path $envFile -Value $content -Encoding UTF8 -NoNewline
# Restreint la lecture du fichier à l'utilisateur courant
icacls $envFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
Write-Host "Fichier .env créé avec des secrets aléatoires. Sauvegardez-le hors du PC (coffre-fort de mots de passe) : sans lui, les sauvegardes ne sont pas exploitables."
