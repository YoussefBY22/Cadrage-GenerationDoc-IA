#!/usr/bin/env bash
# À exécuter sur le serveur isolé, depuis le dossier du paquet : AUCUN accès réseau n'est utilisé.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Vérification de l'intégrité du paquet..."
sha256sum -c SHA256SUMS --quiet

echo "Chargement des images Docker..."
docker load -i images.tar

if [ ! -f .env ]; then
  cp deploy/env.production.example .env
  echo "Fichier .env créé : renseigner POSTGRES_PASSWORD (long, aléatoire) puis relancer ce script." >&2
  exit 1
fi

# --no-build et --pull never : interdit toute tentative de téléchargement
docker compose up -d --no-build --pull never
docker compose ps
