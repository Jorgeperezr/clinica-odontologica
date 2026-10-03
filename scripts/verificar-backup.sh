#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Verifica una copia de seguridad RESTAURÁNDOLA de verdad.
#
# Una copia que nadie ha restaurado nunca no es una copia: es un archivo
# del que se supone algo. Esto lo comprueba: descifra, restaura en una
# base DESECHABLE, cuenta filas en las tablas que importan y la destruye.
#
# Por qué no basta con lo que había. `backup.sh` «verificaba» con
# `gzip -t`, que prueba que el archivo se descomprime y nada más. Un
# volcado cortado a la mitad —disco lleno, contenedor reiniciado, tubería
# rota— comprime perfectamente y pasa esa prueba. Comprobado con un
# volcado partido a propósito: decía «se descifra y descomprime
# correctamente».
#
# Uso:
#   ./scripts/verificar-backup.sh                 # la copia más reciente
#   ./scripts/verificar-backup.sh <archivo.enc>   # una concreta
#
# Devuelve 0 si la copia es restaurable y distinto de 0 si no, para que
# cron pueda avisar:
#
#   # /etc/cron.d/verificar-backup-clinica  (domingos a las 03:00)
#   0 3 * * 0 root cd /ruta/al/repo && ./scripts/verificar-backup.sh \
#       >> /var/log/verificar-backup.log 2>&1 || \
#       mail -s "FALLO: la copia de la clinica NO es restaurable" tu@correo
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# shellcheck source=lib-backup.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-backup.sh"
cargar_entorno
exigir_frase
exigir_openssl

ARCHIVO="${1:-}"
if [ -z "$ARCHIVO" ]; then
    DIR="${BACKUP_DIR:-$RAIZ/backups}"
    # `ls -t` y no `find -printf`: -printf es de GNU y no existe en macOS.
    ARCHIVO=$(ls -t "$DIR"/*.sql.gz.enc 2>/dev/null | head -1 || true)
    if [ -z "$ARCHIVO" ]; then
        echo "✗ No hay ninguna copia en $DIR" >&2
        exit 1
    fi
    echo "→ Copia más reciente: $ARCHIVO"
fi

if [ ! -f "$ARCHIVO" ]; then
    echo "✗ No existe: $ARCHIVO" >&2
    exit 1
fi

echo "→ Conexión: $(describir_conexion)"

# ── Base desechable ──────────────────────────────────────────────────
# El nombre lleva marca de tiempo y un prefijo inconfundible. Y aun así
# se comprueba que NO coincide con la base real: una prueba de
# restauración que por un descuido escriba sobre producción es peor que
# no tener prueba ninguna.
BASE_PRUEBA="verif_backup_$(date +%Y%m%d_%H%M%S)_$$"

if [ "$BASE_PRUEBA" = "$POSTGRES_DB" ]; then
    echo "✗ La base de prueba coincide con la real. Abortado." >&2
    exit 1
fi

limpiar() {
    consultar postgres -q -c "DROP DATABASE IF EXISTS \"$BASE_PRUEBA\";" >/dev/null 2>&1 || true
}
trap limpiar EXIT

# ── 1. ¿El volcado está completo? ────────────────────────────────────
echo "→ Comprobando que el volcado no esté truncado…"
if ! dump_completo "$ARCHIVO"; then
    echo "✗ El volcado NO termina con «${MARCA_FIN}»." >&2
    echo "  Se cortó a medias. Esta copia NO es restaurable." >&2
    exit 1
fi
echo "✓ El volcado está completo."

# ── 2. Restaurar de verdad ───────────────────────────────────────────
echo "→ Restaurando en la base desechable «${BASE_PRUEBA}»…"
consultar postgres -q -c "CREATE DATABASE \"$BASE_PRUEBA\";" >/dev/null

ERRORES=$(mktemp)
if ! descifrar "$ARCHIVO" | gunzip | consultar "$BASE_PRUEBA" --quiet -v ON_ERROR_STOP=1 \
        > /dev/null 2> "$ERRORES"; then
    echo "✗ La restauración FALLÓ:" >&2
    head -20 "$ERRORES" >&2
    rm -f "$ERRORES"
    exit 1
fi
rm -f "$ERRORES"
echo "✓ Restauración completada sin errores."

# ── 3. ¿Están los datos que deben estar? ─────────────────────────────
# Que la restauración no dé error no basta: un volcado del esquema sin
# datos también se restaura limpiamente y sería una copia inútil.
echo "→ Contando filas en las tablas que importan…"

TABLAS="patients_patient clinical_clinicalrecord billing_payment accounts_user common_tenant"
FALLOS=0
for tabla in $TABLAS; do
    filas=$(consultar "$BASE_PRUEBA" -tAc \
        "SELECT count(*) FROM $tabla;" 2>/dev/null | tr -d '[:space:]' || echo "ERROR")
    if [ "$filas" = "ERROR" ]; then
        echo "  ✗ $tabla — la tabla no existe en la copia"
        FALLOS=$((FALLOS + 1))
    else
        echo "  · $tabla: $filas"
    fi
done

if [ "$FALLOS" -gt 0 ]; then
    echo "✗ Faltan $FALLOS tabla(s) en la copia." >&2
    exit 1
fi

# `common_tenant` sin filas significa que ni siquiera hay una clínica: el
# volcado trae el esquema y poco más.
CLINICAS=$(consultar "$BASE_PRUEBA" -tAc "SELECT count(*) FROM common_tenant;" | tr -d '[:space:]')
if [ "$CLINICAS" -lt 1 ]; then
    echo "✗ La copia no contiene ninguna clínica: hay esquema pero no datos." >&2
    exit 1
fi

TAMANO=$(du -h "$ARCHIVO" | cut -f1)
cat <<FIN

✓ COPIA VERIFICADA — se restauró de verdad, no solo se descomprimió.
  Archivo : $ARCHIVO ($TAMANO)
  Clínicas: $CLINICAS
  La base desechable «${BASE_PRUEBA}» se destruye al salir.
FIN
