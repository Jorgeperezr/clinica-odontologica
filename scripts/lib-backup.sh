#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Piezas comunes de backup.sh, restore.sh y verificar-backup.sh.
# No se ejecuta suelto: se carga con `source`.
#
# Resuelve dos cosas que estaban mal en los guiones originales:
#
# 1. **El .env se leía del directorio ACTUAL.** `source <(grep ... .env)`
#    solo encuentra el archivo si uno está parado en la raíz del repo.
#    Desde cron, donde el directorio de trabajo es el del usuario, fallaba
#    o —peor— podía leer otro .env. Ahora se resuelve la raíz del repo a
#    partir de la ruta del propio guion.
#
# 2. **Todo pasaba por `docker compose exec`.** Si no hay demonio de
#    Docker —un Mac sin Docker Desktop, una VM sin privilegios, un
#    entorno de agente en la nube— no había forma de hacer ni una copia.
#    Ahora se usa Docker si está disponible y `pg_dump`/`psql` locales si
#    no, con el mismo resultado.
# ─────────────────────────────────────────────────────────────────────

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cargar_entorno() {
    local archivo="$RAIZ/.env"
    if [ -f "$archivo" ]; then
        # Se lee el .env SIN evaluarlo. El guion original hacía
        # `source <(grep ... .env)`, y eso ejecuta cada línea como si
        # fuera un comando: con
        #
        #     BACKUP_PASSPHRASE=frase de cifrado con espacios
        #
        # bash intenta ejecutar `de` y falla con «de: command not found»,
        # un mensaje que no dice nada de lo que pasa. Y una frase de
        # cifrado es justo lo que alguien escribe como frase.
        #
        # Aquí se parte por el PRIMER `=` y se asigna el resto tal cual,
        # quitando solo las comillas envolventes si las hay.
        local linea clave valor
        while IFS= read -r linea; do
            case "$linea" in
                POSTGRES_DB=*|POSTGRES_USER=*|POSTGRES_PASSWORD=*|\
                POSTGRES_HOST=*|POSTGRES_PORT=*|BACKUP_PASSPHRASE=*) ;;
                *) continue ;;
            esac
            clave="${linea%%=*}"
            valor="${linea#*=}"
            # Comillas envolventes, si el .env las trae.
            case "$valor" in
                \"*\") valor="${valor#\"}"; valor="${valor%\"}" ;;
                "'"'"'"*"'"'"'") valor="${valor#"'"'"'}"; valor="${valor%"'"'"'}" ;;
            esac
            # El ENTORNO gana sobre el .env, que es la convención de
            # todo el mundo y lo que hace falta para poder decir
            # `POSTGRES_DB=otra ./scripts/backup.sh` o pasar la frase
            # desde un gestor de secretos sin editar archivos.
            #
            # Estaba al revés, y no era cosmético: una verificación
            # lanzada con la frase equivocada a propósito PASABA, porque
            # el .env la reemplazaba por la buena por detrás. Una prueba
            # que no puede fallar no prueba nada.
            if [ -z "${!clave:-}" ]; then
                printf -v "$clave" '%s' "$valor"
                export "${clave?}"
            fi
        done < "$archivo"
    fi

    POSTGRES_DB="${POSTGRES_DB:-clinica}"
    POSTGRES_USER="${POSTGRES_USER:-clinica}"
    POSTGRES_HOST="${POSTGRES_HOST:-127.0.0.1}"
    POSTGRES_PORT="${POSTGRES_PORT:-5432}"
}

exigir_frase() {
    if [ -z "${BACKUP_PASSPHRASE:-}" ]; then
        cat >&2 <<FIN
ERROR: falta BACKUP_PASSPHRASE (en $RAIZ/.env o en el entorno).
Genérala con: python3 -c "import secrets; print(secrets.token_urlsafe(32))"

GUÁRDALA APARTE DE LA COPIA. Sin ella el archivo es irrecuperable: ese es
justamente el punto del cifrado, no un efecto secundario.
FIN
        exit 1
    fi
}

# ── Cómo se llega a PostgreSQL ───────────────────────────────────────
# Docker si lo hay; si no, los clientes locales. Se decide una vez y se
# informa, para que nadie tenga que adivinar qué base se tocó.

hay_docker() {
    command -v docker >/dev/null 2>&1 \
        && docker compose version >/dev/null 2>&1 \
        && docker compose -f "$RAIZ/${COMPOSE_FILE:-docker-compose.yml}" ps postgres >/dev/null 2>&1
}

describir_conexion() {
    if hay_docker; then
        echo "docker compose (${COMPOSE_FILE:-docker-compose.yml})"
    else
        echo "$POSTGRES_HOST:$POSTGRES_PORT (cliente local)"
    fi
}

# Ejecuta pg_dump contra la base indicada, escribiendo SQL por stdout.
volcar() {
    local base="$1"
    if hay_docker; then
        docker compose -f "$RAIZ/${COMPOSE_FILE:-docker-compose.yml}" exec -T postgres \
            pg_dump -U "$POSTGRES_USER" --clean --if-exists "$base"
    else
        PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
            -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            --clean --if-exists "$base"
    fi
}

# Ejecuta psql contra la base indicada. Los argumentos extra van a psql.
consultar() {
    local base="$1"; shift
    if hay_docker; then
        docker compose -f "$RAIZ/${COMPOSE_FILE:-docker-compose.yml}" exec -T postgres \
            psql -U "$POSTGRES_USER" -d "$base" "$@"
    else
        PGPASSWORD="${POSTGRES_PASSWORD:-}" psql \
            -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            -d "$base" "$@"
    fi
}

# macOS no trae OpenSSL: trae LibreSSL, y su `enc` no siempre acepta
# `-pbkdf2`. Sin esa opción el cifrado cae a la derivación de clave
# antigua de OpenSSL (una pasada de MD5), que es mucho más débil. Peor
# aún: fallaría al DESCIFRAR una copia hecha en el servidor con pbkdf2,
# y eso se descubriría el día que haga falta restaurar. Se comprueba
# antes de escribir nada.
exigir_openssl() {
    if ! openssl enc -aes-256-cbc -pbkdf2 -iter 2 -pass pass:x \
            -in /dev/null -out /dev/null 2>/dev/null; then
        cat >&2 <<FIN
ERROR: este openssl no acepta -pbkdf2.

  $(openssl version 2>/dev/null || echo "openssl no encontrado")

Suele pasar en macOS, que trae LibreSSL en lugar de OpenSSL. Sin
-pbkdf2 el cifrado usaría una derivación de clave mucho más débil y,
sobre todo, no podría descifrar las copias hechas en el servidor.

Solución en macOS:   brew install openssl@3
                     export PATH="\$(brew --prefix openssl@3)/bin:\$PATH"
FIN
        exit 1
    fi
}

cifrar() {
    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
        -pass "pass:$BACKUP_PASSPHRASE"
}

descifrar() {
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
        -pass "pass:$BACKUP_PASSPHRASE" -in "$1"
}

# ── Comprobación de que el volcado está COMPLETO ─────────────────────
#
# `gzip -t` NO sirve para esto, aunque es lo que hacía backup.sh: prueba
# que el archivo se descomprime, no que el SQL de dentro esté entero. Un
# volcado cortado a la mitad —disco lleno, contenedor reiniciado, tubería
# rota— comprime perfectamente y pasa esa prueba. Comprobado.
#
# `pg_dump` cierra siempre con una línea de fin. Si no está, el volcado
# se truncó, y eso sí se detecta.
MARCA_FIN="PostgreSQL database dump complete"

dump_completo() {
    descifrar "$1" | gunzip 2>/dev/null | tail -5 | grep -q "$MARCA_FIN"
}
