#!/usr/bin/env bash
# Restauration : vérifie les empreintes AVANT toute écriture, puis remplace la base et les pièces.
# Usage : deploy/restore.sh <dossier_de_sauvegarde> --yes
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:?dossier de sauvegarde requis}"
[ "${2:-}" = "--yes" ] || { echo "Opération destructive : relancer avec --yes" >&2; exit 2; }
set -a; . ./.env; set +a

(cd "$SRC" && sha256sum -c SHA256SUMS)   # s'arrête (set -e) si une empreinte diffère

docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$SRC/db.dump"
docker compose exec -T api sh -c 'rm -rf /data/uploads/* && tar -C /data -xf -' < "$SRC/uploads.tar"

echo "Restauration terminée depuis $SRC"
