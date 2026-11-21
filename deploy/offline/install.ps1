# Installation hors ligne (Windows), depuis le dossier du paquet : aucun accès réseau.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
foreach ($line in Get-Content SHA256SUMS) {
    $hash, $name = $line -split '\s+', 2
    $name = $name.Trim().TrimStart('*')
    if ((Get-FileHash $name -Algorithm SHA256).Hash.ToLower() -ne $hash) { throw "Empreinte différente : $name" }
}
docker load -i images.tar
if (-not (Test-Path .env)) {
    Copy-Item deploy\env.production.example .env
    throw "Fichier .env créé : renseigner POSTGRES_PASSWORD puis relancer."
}
docker compose up -d --no-build --pull never
docker compose ps
