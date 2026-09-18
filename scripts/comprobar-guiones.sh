#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Revisión de los guiones de shell del repositorio.
#
# Existe por un fallo concreto que costó una tarde y que no se ve en
# Linux. Esta línea:
#
#     echo "Creando entorno virtual con $INTERPRETE…"
#
# funciona en el bash 5 de Linux y revienta en el bash de macOS con
#
#     start-local.sh: line 130: INTERPRETE?: unbound variable
#
# El nombre de la variable termina donde termina lo que bash considera
# parte de un identificador. Con `set -u` y un bash antiguo tratando los
# bytes del carácter que sigue —aquí los tres del puntos suspensivos «…»,
# pero vale cualquier letra acentuada, «»  o ✓— como si fueran parte del
# nombre, la variable que busca ya no es $INTERPRETE sino otra que no
# existe. Y el mensaje nombra esa otra, así que no se parece a su causa.
#
# Las llaves lo cierran sin ambigüedad en cualquier bash:
#
#     echo "Creando entorno virtual con ${INTERPRETE}…"
#
# Esto no es una manía de estilo: era el mismo fallo en cinco guiones,
# entre ellos los tres de las copias de seguridad.
#
# Uso:   bash scripts/comprobar-guiones.sh
# Devuelve 0 si todo está bien y 1 si hay algo que corregir.
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FALLOS=0

echo "▶ Sintaxis"
for guion in "$RAIZ"/scripts/*.sh; do
    if bash -n "$guion" 2>/dev/null; then
        printf '  ✓ %s\n' "$(basename "$guion")"
    else
        printf '  ✗ %s\n' "$(basename "$guion")"
        bash -n "$guion" 2>&1 | sed 's/^/      /'
        FALLOS=$((FALLOS + 1))
    fi
done

echo ""
echo "▶ Variables pegadas a un carácter no ASCII"
# LC_ALL=C para que la comparación sea byte a byte y `[:print:]` no
# incluya los acentuados: así cualquier byte de un carácter multibyte
# cae fuera y se detecta. `[:space:]` evita señalar un tabulador.
# El `(^|[^\])` de delante descarta un `\$` escapado, que no se expande
# y por tanto no puede fallar. El segundo grep descarta los comentarios:
# este mismo archivo explica el fallo mostrandolo, y se senalaria a si
# mismo.
PEGADAS=$(LC_ALL=C grep -nE '(^|[^\])\$[A-Za-z_][A-Za-z0-9_]*[^[:print:][:space:]]' \
    "$RAIZ"/scripts/*.sh 2>/dev/null \
    | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' || true)

if [ -n "$PEGADAS" ]; then
    echo "$PEGADAS" | while IFS= read -r linea; do
        printf '  ✗ %s\n' "$linea"
    done
    echo ""
    echo "  Ponles llaves: \"\$VARIABLE…\" → \"\${VARIABLE}…\""
    FALLOS=$((FALLOS + 1))
else
    echo "  ✓ Ninguna"
fi

echo ""
if [ "$FALLOS" -gt 0 ]; then
    echo "✗ $FALLOS comprobación(es) con fallos."
    exit 1
fi
echo "✓ Los guiones están bien."
