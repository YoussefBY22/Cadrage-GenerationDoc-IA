#!/usr/bin/env bash
# À exécuter sur une machine AVEC Internet : prépare le paquet à copier sur le serveur isolé.
# Résultat : bundle/ (wheelhouse Python, images Docker, compose, scripts, SHA256SUMS).
set -euo pipefail
cd "$(dirname "$0")/../.."
OUT="${1:-bundle}"
rm -rf "$OUT" && mkdir -p "$OUT/wheelhouse" "$OUT/deploy"

# 1. Bibliothèques Python (utile pour un lancement sans Docker)
python3 -m pip download -r backend/requirements.lock -d "$OUT/wheelhouse"

# 2. Dépendances du front vérifiées (npm ci échoue si package-lock.json est incohérent)
(cd frontend && NEXT_TELEMETRY_DISABLED=1 npm ci)

# 3. Images : construction des nôtres, récupération des images de base, export unique
export POSTGRES_DB=build POSTGRES_USER=build POSTGRES_PASSWORD=build   # valeurs factices : rien n'est lancé
docker compose --profile llm build
docker compose --profile llm pull db proxy ollama
IMAGES=$(docker compose --profile llm config --images | sort -u)
# shellcheck disable=SC2086
docker save -o "$OUT/images.tar" $IMAGES

# 4. Fichiers de déploiement
cp docker-compose.yml "$OUT/"
cp -r db "$OUT/db"
cp deploy/nginx.conf deploy/env.production.example deploy/backup.sh deploy/restore.sh \
   deploy/backup.ps1 deploy/restore.ps1 "$OUT/deploy/"
cp deploy/offline/install.sh deploy/offline/install.ps1 "$OUT/deploy/"

(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "Paquet prêt : $OUT (copier tout le dossier sur le serveur, puis deploy/install.sh)"
