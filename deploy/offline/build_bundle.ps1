# Préparation du paquet hors ligne (Windows, machine AVEC Internet).
param([string]$Out = "bundle")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
New-Item -ItemType Directory -Force "$Out\wheelhouse", "$Out\deploy" | Out-Null

py -3.12 -m pip download -r backend\requirements.lock -d "$Out\wheelhouse"
Push-Location frontend; $env:NEXT_TELEMETRY_DISABLED = "1"; npm ci; Pop-Location

$env:POSTGRES_DB = "build"; $env:POSTGRES_USER = "build"; $env:POSTGRES_PASSWORD = "build"   # factices
docker compose --profile llm build
docker compose --profile llm pull db proxy ollama
$images = docker compose --profile llm config --images | Sort-Object -Unique
docker save -o "$Out\images.tar" $images

Copy-Item docker-compose.yml $Out
Copy-Item -Recurse db "$Out\db"
Copy-Item deploy\nginx.conf, deploy\env.production.example, deploy\backup.sh, deploy\restore.sh, `
    deploy\backup.ps1, deploy\restore.ps1, deploy\offline\install.sh, deploy\offline\install.ps1 "$Out\deploy"
Get-ChildItem $Out -Recurse -File | Where-Object Name -ne SHA256SUMS | ForEach-Object {
    "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(),
        (Resolve-Path -Relative $_.FullName -RelativeBasePath $Out).Replace('\', '/') } |
    Set-Content -Encoding ascii "$Out\SHA256SUMS"
Write-Host "Paquet prêt : $Out"
