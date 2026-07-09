#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Restauración de un backup cifrado generado por backup.sh.
# ⚠ REEMPLAZA los datos actuales de la base con los del backup.
#
# Uso:
#   ./scripts/restore.sh backups/clinica-2026-07-09_0200.sql.gz.enc
#   COMPOSE_FILE=docker-compose.prod.yml ./scripts/restore.sh <archivo>
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

if [ $# -ne 1 ] || [ ! -f "$1" ]; then
  echo "Uso: $0 <archivo .sql.gz.enc>"
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
source <(grep -E "^(POSTGRES_DB|POSTGRES_USER|BACKUP_PASSPHRASE)=" .env)

if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
  echo "ERROR: falta BACKUP_PASSPHRASE en el .env (la misma con la que se cifró)."
  exit 1
fi

echo "⚠  ATENCIÓN: esto REEMPLAZA los datos actuales de '$POSTGRES_DB'"
echo "   con el contenido de: $1"
read -p "   Escribe RESTAURAR para continuar: " CONFIRM
if [ "$CONFIRM" != "RESTAURAR" ]; then
  echo "Cancelado."
  exit 1
fi

echo "→ Descifrando y restaurando…"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "pass:$BACKUP_PASSPHRASE" -in "$1" \
  | gunzip \
  | docker compose -f "$COMPOSE_FILE" exec -T postgres \
      psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" --quiet

echo "→ Reiniciando servicios para tomar el estado restaurado…"
docker compose -f "$COMPOSE_FILE" restart django-api celery-worker celery-beat

echo "✓ Restauración completa. Verifica entrando al panel."
