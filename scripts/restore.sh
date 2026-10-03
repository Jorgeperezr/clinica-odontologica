#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Restauración de una copia cifrada generada por backup.sh.
# ⚠ REEMPLAZA los datos actuales de la base con los de la copia.
#
# Si lo que quieres es COMPROBAR que la copia sirve, no uses esto: usa
# `verificar-backup.sh`, que restaura en una base desechable y no toca
# los datos reales.
#
# Uso:
#   ./scripts/restore.sh backups/clinica-2026-07-09_0200.sql.gz.enc
#   COMPOSE_FILE=docker-compose.prod.yml ./scripts/restore.sh <archivo>
#
# Funciona con Docker y sin él.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# shellcheck source=lib-backup.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-backup.sh"

if [ $# -ne 1 ] || [ ! -f "$1" ]; then
    echo "Uso: $0 <archivo .sql.gz.enc>" >&2
    exit 1
fi

cargar_entorno
exigir_frase
exigir_openssl

# Comprobar ANTES de destruir nada. Descubrir que la copia estaba
# truncada después de haber borrado la base es la peor secuencia posible,
# y es la que permitía el guion anterior.
echo "→ Comprobando que la copia esté completa…"
if ! dump_completo "$1"; then
    echo "✗ El volcado está TRUNCADO o la frase de cifrado no es la correcta." >&2
    echo "  NO se ha tocado la base de datos." >&2
    exit 1
fi
echo "✓ La copia se descifra y está completa."

echo ""
echo "⚠  ATENCIÓN: esto REEMPLAZA los datos actuales de «${POSTGRES_DB}»"
echo "   en $(describir_conexion)"
echo "   con el contenido de: $1"
read -r -p "   Escribe RESTAURAR para continuar: " CONFIRM
if [ "$CONFIRM" != "RESTAURAR" ]; then
    echo "Cancelado."
    exit 1
fi

echo "→ Descifrando y restaurando…"
descifrar "$1" | gunzip | consultar "$POSTGRES_DB" --quiet

if hay_docker; then
    echo "→ Reiniciando servicios para tomar el estado restaurado…"
    docker compose -f "$RAIZ/${COMPOSE_FILE:-docker-compose.yml}" \
        restart django-api celery-worker celery-beat
else
    echo "→ Sin Docker: reinicia a mano los procesos de Django y Celery."
fi

echo "✓ Restauración completa. Verifica entrando al panel."
