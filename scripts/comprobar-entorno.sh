#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Revisión del entorno de la máquina ANTES de intentar nada.
#
# Por qué existe. La verificación de las copias de seguridad tiene un
# camino que no se puede probar en Linux: en macOS, `openssl` no es
# OpenSSL sino LibreSSL, y su `enc` puede no aceptar `-pbkdf2`. Si no lo
# acepta, una copia hecha en el Mac usaría una derivación de clave
# antigua y —lo que de verdad importa— no podría descifrar las copias
# hechas en el servidor. Eso se descubriría el día de restaurar, que es
# el peor día para descubrir nada.
#
# Comprueba, además, todo lo demás que hace falta para levantar el
# proyecto, y para cada cosa que falta dice qué hacer. No modifica nada:
# no instala, no arranca servicios, no escribe archivos.
#
# Uso:   bash scripts/comprobar-entorno.sh
#
# Devuelve 0 si se puede trabajar y 1 si hay algo que lo impide.
# ─────────────────────────────────────────────────────────────────────
set -uo pipefail   # sin -e: aquí un fallo es un DATO, no un motivo para parar

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BLOQUEOS=0
AVISOS=0

ok()     { printf '  ✓ %s\n' "$*"; }
falta()  { printf '  ✗ %s\n' "$*"; BLOQUEOS=$((BLOQUEOS + 1)); }
aviso()  { printf '  ! %s\n' "$*"; AVISOS=$((AVISOS + 1)); }
nota()   { printf '      %s\n' "$*"; }
titulo() { printf '\n%s\n' "$*"; }

# Compara versiones sin depender de `sort -V`, que en macOS no siempre
# está. Devuelve 0 si $1 >= $2.
version_minima() {
    local tengo="$1" quiero="$2"
    local a b
    IFS=. read -r a b _ <<< "$tengo"
    local qa qb
    IFS=. read -r qa qb _ <<< "$quiero"
    a=${a:-0}; b=${b:-0}; qa=${qa:-0}; qb=${qb:-0}
    [ "$a" -gt "$qa" ] && return 0
    [ "$a" -lt "$qa" ] && return 1
    [ "${b:-0}" -ge "$qb" ]
}

echo "════════════════════════════════════════════════════════════════"
echo " Entorno para clinica-odontologica"
echo "════════════════════════════════════════════════════════════════"

# ── 0. Dónde estamos ─────────────────────────────────────────────────
# Esto primero porque es el fallo más fácil de cometer y el que peor se
# explica: ejecutar los guiones desde la carpeta personal en lugar de
# desde el repositorio da «not a git repository» o «No such file or
# directory», mensajes que parecen decir que algo está roto cuando lo
# único que pasa es que hay que entrar a la carpeta.
titulo "Ubicación"
if [ -d "$RAIZ/.git" ]; then
    ok "Repositorio en $RAIZ"
    RAMA=$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
    nota "rama actual: $RAMA"
else
    aviso "No parece un clon de git: $RAIZ"
    nota "Los guiones funcionan igual, pero no habrá historial."
fi

SO=$(uname -s)
if [ "$SO" = "Darwin" ]; then
    nota "macOS $(sw_vers -productVersion 2>/dev/null || echo '')  ($(uname -m))"
else
    nota "$SO $(uname -m)"
fi
# La versión de bash y la configuración regional se anotan porque un
# fallo de estos guiones puede depender de las dos: macOS trae bash 3.2
# —de 2007— y el manejo de los caracteres no ASCII cambia con la
# configuración regional. Si algo falla solo en una máquina, esta línea
# suele ser la primera pista.
nota "bash ${BASH_VERSION:-?}  ·  LANG=${LANG:-sin fijar}"

# ── 1. openssl y -pbkdf2 ─────────────────────────────────────────────
titulo "Cifrado de las copias (openssl)"
if ! command -v openssl >/dev/null 2>&1; then
    falta "No hay openssl en el PATH."
    nota "macOS:  brew install openssl@3"
else
    VER=$(openssl version 2>/dev/null)
    if openssl enc -aes-256-cbc -pbkdf2 -iter 2 -pass pass:x \
            -in /dev/null -out /dev/null 2>/dev/null; then
        ok "$VER — acepta -pbkdf2"
        # Que acepte la opción no basta: lo que importa es que una copia
        # hecha aquí se pueda descifrar, y al revés. Se comprueba de ida
        # y vuelta con un texto de prueba.
        PRUEBA=$(printf 'clinica' \
            | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass pass:prueba 2>/dev/null \
            | openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass pass:prueba 2>/dev/null)
        if [ "$PRUEBA" = "clinica" ]; then
            ok "Cifra y descifra con los mismos parámetros que backup.sh"
        else
            falta "Cifra pero NO descifra lo que acaba de cifrar."
            nota "No uses este openssl para las copias. brew install openssl@3"
        fi
    else
        falta "$VER — NO acepta -pbkdf2"
        nota "Es lo típico de LibreSSL, el openssl que trae macOS."
        nota "Sin -pbkdf2 las copias usarían una derivación de clave mucho"
        nota "más débil y no podrían descifrar las hechas en el servidor."
        nota "Solución:  brew install openssl@3"
        nota '           export PATH="$(brew --prefix openssl@3)/bin:$PATH"'
    fi
fi

# ── 2. PostgreSQL ────────────────────────────────────────────────────
titulo "PostgreSQL"
HAY_DOCKER=0
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    HAY_DOCKER=1
    ok "Docker en marcha — $(docker --version 2>/dev/null | cut -d, -f1)"
    if docker compose version >/dev/null 2>&1; then
        ok "docker compose disponible"
    else
        aviso "docker sin el plugin «compose»; los guiones usarán los clientes locales."
    fi
elif command -v docker >/dev/null 2>&1; then
    aviso "Docker instalado pero el demonio no responde (¿Docker Desktop cerrado?)."
    nota "Se puede trabajar igual con PostgreSQL local."
else
    aviso "No hay Docker. Se puede trabajar con PostgreSQL local."
fi

for prog in psql pg_dump; do
    if command -v "$prog" >/dev/null 2>&1; then
        ok "$prog $("$prog" --version 2>/dev/null | awk '{print $3}')"
    elif [ "$HAY_DOCKER" = 1 ]; then
        aviso "No hay $prog local; se usará el del contenedor."
    else
        falta "No hay $prog ni Docker: las copias no se pueden hacer."
        nota "macOS:  brew install postgresql@16"
    fi
done

# ── 3. Python ────────────────────────────────────────────────────────
#
# Aquí hay techo, y no es una manía. Django 5.0.9 declara soporte para
# 3.10, 3.11 y 3.12 y nada más; el contenedor del proyecto y el CI usan
# 3.12. Un Python más nuevo instala igual —`Requires-Python: >=3.10` no
# pone límite— y luego falla por su cuenta, en sitios que no se parecen
# a la causa.
#
# Una comprobación con mínimo y sin techo no es una comprobación: avisa
# de lo viejo y calla ante lo que nadie ha probado nunca. Esta revisión
# daba «✓ python3 3.14» tan contenta.
#
# Y no basta con mirar a qué apunta `python3`: lo que importa es si hay
# ALGÚN intérprete servible en la máquina, porque start-local.sh busca
# uno compatible antes de caer en el de por defecto.
PY_BUENO="3.12"
titulo "Python (la API)"
PY_ELEGIDO=""
# Se deja sobrescribir para poder probar el camino del «no hay ninguno»
# sin desmontar la máquina, y para quien tenga los intérpretes con otro
# nombre (pyenv, asdf).
for cmd in ${PY_CANDIDATOS:-python3.12 python3.11 python3.10}; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_ELEGIDO="$cmd"
        break
    fi
done

if [ -n "$PY_ELEGIDO" ]; then
    ok "$PY_ELEGIDO $("$PY_ELEGIDO" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)"
    nota "start-local.sh usará este, no el de por defecto."
    # En Debian y derivados `venv` viene en un paquete aparte, y su
    # ausencia se descubre a mitad del arranque con un error que habla
    # de `ensurepip`. Mejor saberlo ahora.
    if ! "$PY_ELEGIDO" -c 'import venv, ensurepip' >/dev/null 2>&1; then
        falta "$PY_ELEGIDO no puede crear entornos virtuales"
        nota "Linux:  apt install ${PY_ELEGIDO}-venv"
        nota "Sin eso no hay dónde instalar las dependencias."
    fi
elif command -v python3 >/dev/null 2>&1; then
    PY=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
    if ! version_minima "$PY" 3.10; then
        falta "python3 $PY — Django 5.0 necesita 3.10 o superior"
        nota "macOS:  brew install python@$PY_BUENO"
    elif version_minima "$PY" 3.13; then
        falta "python3 $PY — por encima de lo que soporta Django 5.0 (hasta 3.12)"
        nota "No hay ningún 3.10, 3.11 ni 3.12 en la máquina, así que"
        nota "start-local.sh no tendría con qué trabajar."
        nota "macOS:  brew install python@$PY_BUENO"
        nota "No hace falta quitar el $PY: conviven, y el guion elige."
    else
        ok "python3 $PY"
    fi
else
    falta "No hay python3."
    nota "macOS:  brew install python@$PY_BUENO"
fi

# ── 4. Node ──────────────────────────────────────────────────────────
NODE_BUENO="20"
titulo "Node (el panel)"
if command -v node >/dev/null 2>&1; then
    NODE=$(node -v 2>/dev/null | tr -d 'v')
    if ! version_minima "$NODE" 18.17; then
        falta "node $NODE — Next.js 14 necesita 18.17 o superior"
        nota "macOS:  brew install node@$NODE_BUENO"
    elif version_minima "$NODE" 23; then
        # Aviso y no bloqueo: Next 14 no declara techo y con Node nuevo
        # suele funcionar. Pero el par probado es otro, así que si el
        # panel hace algo raro conviene saber por dónde empezar a mirar
        # en vez de buscar el fallo en el código.
        aviso "node $NODE — funciona, pero el par probado es Node $NODE_BUENO"
        nota "Next.js 14 es de antes que esta versión de Node y no la"
        nota "declara. Si el panel falla al compilar o al arrancar, prueba:"
        nota "  brew install node@$NODE_BUENO"
    else
        ok "node $NODE"
    fi
else
    falta "No hay node."
    nota "macOS:  brew install node@$NODE_BUENO"
fi

# ── 5. Configuración ─────────────────────────────────────────────────
titulo "Configuración"
if [ -f "$RAIZ/.env" ]; then
    ok ".env presente"
    # Se mira SI está la clave, nunca su valor: este informe se pega en
    # un chat o en un correo.
    if grep -q '^BACKUP_PASSPHRASE=.\+' "$RAIZ/.env" 2>/dev/null; then
        ok "BACKUP_PASSPHRASE definida (no se muestra)"
    else
        aviso "Sin BACKUP_PASSPHRASE: backup.sh no arrancará."
        nota 'Genérala:  python3 -c "import secrets; print(secrets.token_urlsafe(32))"'
        nota "Y guárdala APARTE de las copias."
    fi
else
    aviso "No hay .env en la raíz."
    nota "Para desarrollo no hace falta: start-local.sh trae sus valores."
    nota "Para hacer copias, sí."
fi

# ── 6. Puertos ───────────────────────────────────────────────────────
# Un puerto ocupado no impide trabajar, pero explica de antemano un
# «Address already in use» que de otro modo aparece a mitad del arranque.
titulo "Puertos"
if command -v lsof >/dev/null 2>&1; then
    for puerto in 3000 8000 5432; do
        QUIEN=$(lsof -nP -iTCP:"$puerto" -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1}')
        if [ -n "$QUIEN" ]; then
            aviso "$puerto ocupado por «${QUIEN}»"
        else
            ok "$puerto libre"
        fi
    done
else
    nota "Sin lsof: no se comprueban los puertos."
fi

# ── Resumen ──────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
if [ "$BLOQUEOS" -gt 0 ]; then
    echo " $BLOQUEOS cosa(s) que impiden trabajar, $AVISOS aviso(s)."
    echo " Resuelve las marcadas con ✗ y vuelve a pasar esta revisión."
    echo "════════════════════════════════════════════════════════════════"
    exit 1
fi
if [ "$AVISOS" -gt 0 ]; then
    echo " Todo lo esencial está. $AVISOS aviso(s), ninguno bloquea."
else
    echo " Entorno completo."
fi
echo ""
echo " Siguiente paso:   bash scripts/start-local.sh"
echo " Y en el navegador http://localhost:3000  (localhost, NO 127.0.0.1)"
echo "════════════════════════════════════════════════════════════════"
exit 0
