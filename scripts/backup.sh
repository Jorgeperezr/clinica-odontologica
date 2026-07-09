#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Backup CIFRADO de la base de datos (pacientes, registros clínicos,
# pagos — todo). Genera un archivo .sql.gz.enc con AES-256.
#
# Uso:
#   ./scripts/backup.sh                      # entorno de desarrollo
#   COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh   # producción
#
# Requiere BACKUP_PASSPHRASE en el .env (la clave de cifrado).
# GUARDAR ESA CLAVE EN UN LUGAR SEPARADO DEL BACKUP: sin ella, el
# backup es irrecuperable (ese es el punto del cifrado).
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"

# Leer credenciales del .env
source <(grep -E "^(POSTGRES_DB|POSTGRES_USER|BACKUP_PASSPHRASE)=" .env)

if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
  echo "ERROR: falta BACKUP_PASSPHRASE en el .env"
  echo "Generala con: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
  exit 1
fi

STAMP=$(date +%Y-%m-%d_%H%M)
OUTFILE="$BACKUP_DIR/clinica-$STAMP.sql.gz.enc"

echo "→ Exportando la base '$POSTGRES_DB'…"
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB" \
  | gzip \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
      -pass "pass:$BACKUP_PASSPHRASE" \
  > "$OUTFILE"

SIZE=$(du -h "$OUTFILE" | cut -f1)
echo "✓ Backup cifrado: $OUTFILE ($SIZE)"
echo ""
echo "Verificación de integridad (descifra sin restaurar):"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "pass:$BACKUP_PASSPHRASE" -in "$OUTFILE" | gzip -t \
  && echo "✓ El archivo se descifra y descomprime correctamente."
echo ""
echo "IMPORTANTE: copiar $OUTFILE a un destino EXTERNO (disco USB,"
echo "Google Drive, etc.). Un backup en la misma máquina no es backup."
