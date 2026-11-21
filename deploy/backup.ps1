# Sauvegarde Windows : base (pg_dump) + pièces importées + empreintes SHA-256.
# Usage : .\deploy\backup.ps1 [-Out backups]
param([string]$Out = "backups")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2; Set-Item "env:$($k.Trim())" $v }

$dest = Join-Path $Out ("cadrage-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ"))
New-Item -ItemType Directory -Force $dest | Out-Null
# cmd /c : redirection binaire sûre (PowerShell 5.1 altère les flux d'octets)
cmd /c "docker compose exec -T db pg_dump -U $env:POSTGRES_USER -d $env:POSTGRES_DB -Fc > `"$dest\db.dump`""
if ($LASTEXITCODE -ne 0) { throw "pg_dump a échoué" }
cmd /c "docker compose exec -T api tar -C /data -cf - uploads > `"$dest\uploads.tar`""
if ($LASTEXITCODE -ne 0) { throw "archive des pièces échouée" }
$lines = foreach ($f in "db.dump", "uploads.tar") {
    "{0}  {1}" -f (Get-FileHash (Join-Path $dest $f) -Algorithm SHA256).Hash.ToLower(), $f }
$lines | Set-Content -Encoding ascii (Join-Path $dest "SHA256SUMS")
Write-Host "Sauvegarde écrite dans $dest"
