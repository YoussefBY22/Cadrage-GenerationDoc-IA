#!/usr/bin/env bash
# Sauvegarde : base (pg_dump) + pièces importées + empreintes. Usage : deploy/backup.sh [dossier_de_sortie]
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

DEST="${1:-backups}/cadrage-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DEST/db.dump"
docker compose exec -T api tar -C /data -cf - uploads > "$DEST/uploads.tar"
(cd "$DEST" && sha256sum db.dump uploads.tar > SHA256SUMS)

echo "Sauvegarde écrite dans $DEST"
