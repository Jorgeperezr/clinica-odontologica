#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Copia de seguridad CIFRADA de la base de datos completa (pacientes,
# registros clínicos, pagos — todo, y de todas las clínicas). Genera un
# archivo .sql.gz.enc con AES-256.
#
# Ojo con la diferencia, que importa: esto es una copia a nivel de
# PLATAFORMA, la hace quien administra el servidor y contiene los datos
# de todas las clínicas. La del panel (Configuración → Copia de
# seguridad) la hace la administración de UNA clínica y solo lleva los
# datos de esa clínica. No son sustitutas la una de la otra.
#
# Uso:
#   ./scripts/backup.sh                      # desarrollo
#   COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh   # producción
#
# Funciona con Docker y sin él: si no hay demonio, usa el pg_dump local.
#
# Requiere BACKUP_PASSPHRASE en el .env.
# GUARDAR ESA CLAVE APARTE DE LA COPIA: sin ella el archivo es
# irrecuperable, que es justamente el punto del cifrado.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# shellcheck source=lib-backup.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-backup.sh"
cargar_entorno
exigir_frase
exigir_openssl

BACKUP_DIR="${BACKUP_DIR:-$RAIZ/backups}"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y-%m-%d_%H%M)
OUTFILE="$BACKUP_DIR/clinica-$STAMP.sql.gz.enc"

echo "→ Conexión: $(describir_conexion)"
echo "→ Exportando la base «$POSTGRES_DB»…"

# `set -o pipefail` ya está activo: si pg_dump falla a mitad, la tubería
# entera falla y no se queda un archivo cifrado a medias pareciendo
# válido. Es exactamente el caso que la verificación de abajo caza.
volcar "$POSTGRES_DB" | gzip | cifrar > "$OUTFILE"

SIZE=$(du -h "$OUTFILE" | cut -f1)
echo "✓ Copia cifrada: $OUTFILE ($SIZE)"

# ── Verificación ─────────────────────────────────────────────────────
# Antes aquí había un `gzip -t`, que comprueba que el archivo se
# descomprime y NADA MÁS. Un volcado cortado a la mitad comprime
# perfectamente y pasaba esa prueba: se anunciaba «correcto» una copia
# irrecuperable. Ahora se comprueba que el SQL termine donde debe.
echo "→ Verificando que el volcado esté completo…"
if dump_completo "$OUTFILE"; then
    echo "✓ El volcado se descifra y termina donde debe."
else
    echo "✗ El volcado está TRUNCADO. La copia no sirve." >&2
    echo "  Se conserva el archivo para poder diagnosticar: $OUTFILE" >&2
    exit 1
fi

cat <<FIN

Esta comprobación dice que el archivo está entero, no que sea
restaurable. Para saberlo hay que restaurarlo:

    ./scripts/verificar-backup.sh "$OUTFILE"

Conviene programarlo semanalmente (ver DEPLOY.md). Una copia que nadie
ha restaurado nunca no es una copia: es un archivo del que se supone algo.

IMPORTANTE: copiar el archivo a un destino EXTERNO —disco USB, Drive,
otro servidor—. Una copia en la misma máquina que la base no protege de
lo que más se lleva por delante los datos: que la máquina se pierda.
FIN
