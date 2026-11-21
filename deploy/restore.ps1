# Restauration Windows : vérifie les empreintes AVANT toute écriture.
# Usage : .\deploy\restore.ps1 -Src backups\cadrage-... -Yes
param([Parameter(Mandatory)][string]$Src, [switch]$Yes)
$ErrorActionPreference = "Stop"
if (-not $Yes) { throw "Opération destructive : relancer avec -Yes" }
Set-Location (Join-Path $PSScriptRoot "..")
Get-Content .env | Where-Object { $_ -match '^\s*[A-Z_]+=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2; Set-Item "env:$($k.Trim())" $v }

foreach ($line in Get-Content (Join-Path $Src "SHA256SUMS")) {
    $hash, $name = $line -split '\s+', 2
    $actual = (Get-FileHash (Join-Path $Src $name.Trim()) -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $hash) { throw "Empreinte différente pour $name : sauvegarde corrompue" }
}
cmd /c "docker compose exec -T db pg_restore -U $env:POSTGRES_USER -d $env:POSTGRES_DB --clean --if-exists --no-owner < `"$Src\db.dump`""
if ($LASTEXITCODE -ne 0) { throw "pg_restore a échoué" }
cmd /c "docker compose exec -T api sh -c `"rm -rf /data/uploads/* && tar -C /data -xf -`" < `"$Src\uploads.tar`""
if ($LASTEXITCODE -ne 0) { throw "restauration des pièces échouée" }
Write-Host "Restauration terminée depuis $Src"
