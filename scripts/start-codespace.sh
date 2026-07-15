#!/usr/bin/env bash
#
# Arranque del entorno de desarrollo en GitHub Codespaces.
#
# Al reiniciar un Codespace, GitHub borra el .env (no está versionado) y
# resetea la visibilidad de los puertos a Private — lo que provoca el
# clásico "Failed to fetch" en el login. Este script deja todo listo:
#
#   1. Crea el .env desde .env.example (si no existe).
#   2. Escribe las URLs reales de ESTE Codespace en CSRF/CORS/ALLOWED_HOSTS.
#   3. Pone los puertos 80 y 3000 en Public.
#   4. Levanta los contenedores y aplica migraciones.
#   5. Muestra las URLs de acceso.
#
# Uso:  bash scripts/start-codespace.sh
#
# Es idempotente: se puede correr las veces que haga falta.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "▶ Arrancando el entorno de la clínica…"
echo

# ── 1. .env ──────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✓ .env creado desde .env.example"

    # Clave de Django: aleatoria por entorno (invalida sesiones viejas, es lo correcto)
    SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
    sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=${SECRET}|" .env

    # Clave de cifrado de backups
    PASSPHRASE=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    sed -i "s|^BACKUP_PASSPHRASE=.*|BACKUP_PASSPHRASE=${PASSPHRASE}|" .env
    echo "✓ Claves generadas (Django y backups)"
    echo "  ⚠ Anota tu BACKUP_PASSPHRASE si vas a restaurar backups viejos:"
    echo "    ${PASSPHRASE}"
else
    echo "✓ .env ya existe (no se toca)"
fi
echo

# ── 2. URLs de este Codespace ────────────────────────────────────────
if [ -n "${CODESPACE_NAME:-}" ]; then
    CS80="https://${CODESPACE_NAME}-80.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
    CS3000="https://${CODESPACE_NAME}-3000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
    CS_HOST="${CODESPACE_NAME}-80.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"

    sed -i "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=http://localhost,http://127.0.0.1,${CS80}|" .env
    sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=http://localhost:3000,${CS3000}|" .env
    sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,${CS_HOST}|" .env
    echo "✓ URLs del Codespace escritas en el .env"
    echo "  API:    ${CS80}"
    echo "  Panel:  ${CS3000}"
else
    echo "• No estás en Codespaces: se mantienen las URLs de localhost"
fi
echo

# ── 3. Puertos públicos (causa habitual del "Failed to fetch") ───────
if [ -n "${CODESPACE_NAME:-}" ] && command -v gh >/dev/null 2>&1; then
    if gh codespace ports visibility 80:public 3000:public -c "${CODESPACE_NAME}" 2>/dev/null; then
        echo "✓ Puertos 80 y 3000 en Public"
    else
        echo "⚠ No se pudo cambiar la visibilidad por CLI."
        echo "  Hazlo a mano: pestaña PORTS → clic derecho en 80 y 3000 →"
        echo "  Port Visibility → Public. (Si no, el login dará 'Failed to fetch'.)"
    fi
fi
echo

# ── 4. Contenedores y migraciones ────────────────────────────────────
echo "▶ Levantando contenedores (puede tardar en el primer arranque)…"
docker compose up -d --build

echo
echo "▶ Esperando a que Postgres acepte conexiones…"
for i in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U clinica >/dev/null 2>&1; then
        echo "✓ Postgres listo"
        break
    fi
    sleep 2
done

echo
echo "▶ Aplicando migraciones…"
docker compose exec -T django-api python manage.py migrate

# ── 5. Resumen ───────────────────────────────────────────────────────
echo
echo "─────────────────────────────────────────────"
docker compose ps --format "table {{.Service}}\t{{.Status}}"
echo "─────────────────────────────────────────────"
echo
if [ -n "${CODESPACE_NAME:-}" ]; then
    echo "Panel:    ${CS3000}"
    echo "API/Admin: ${CS80}/admin/"
    echo "Swagger:   ${CS80}/api/v1/schema/swagger-ui/"
else
    echo "Panel:     http://localhost:3000"
    echo "API/Admin: http://localhost/admin/"
fi
echo
echo "Listo. Si el login da 'Failed to fetch', revisa que los puertos"
echo "80 y 3000 estén en Public en la pestaña PORTS."
