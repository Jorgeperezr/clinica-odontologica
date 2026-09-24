#!/usr/bin/env bash
#
# `manage.py` con el entorno de desarrollo ya puesto.
#
#   bash scripts/manage.sh shell
#   bash scripts/manage.sh createsuperuser
#   bash scripts/manage.sh migrate
#
# Existe por un fallo que despista mucho: `settings.py` toma
# `POSTGRES_HOST` con valor por omisión `postgres`, que es el nombre del
# servicio en Docker. Fuera de Docker y fuera de `start-local.sh` —es
# decir, en cualquier terminal nueva— eso revienta con
#
#   could not translate host name "postgres" to address
#
# que no se parece en nada a «te falta una variable de entorno».
#
# ¿Y por qué no un `.env` en la raíz? Porque `docker-compose.yml` lo
# carga con `env_file: .env` en django-api y en celery-worker. Un `.env`
# con `POSTGRES_HOST=127.0.0.1` haría que el contenedor se buscara la
# base a sí mismo. El arreglo cómodo para el Mac rompería Docker, así
# que el entorno se pone aquí y no en un archivo compartido.
#
# Usa el intérprete de `.venv` si existe, que es el que tiene las
# dependencias: el `python3` del sistema no las tiene, y en macOS
# `python` a secas ni siquiera existe.

set -euo pipefail

cd "$(dirname "$0")/.."
RAIZ="$PWD"

export POSTGRES_HOST=${POSTGRES_HOST:-127.0.0.1}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_DB=${POSTGRES_DB:-clinica}
export POSTGRES_USER=${POSTGRES_USER:-clinica}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-clinica}
export DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-dev-only-key-long-enough-for-hmac-validation-0123456789}
export DJANGO_DEBUG=${DJANGO_DEBUG:-True}
export DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1,testserver,10.0.2.2}

if [ -x "${RAIZ}/.venv/bin/python" ]; then
  PY="${RAIZ}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "✗ No encuentro un Python. Ejecuta antes: bash scripts/start-local.sh" >&2
  exit 1
fi

cd "${RAIZ}/django-api"
exec "${PY}" manage.py "$@"
