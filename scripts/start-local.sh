#!/usr/bin/env bash
#
# Arranque del entorno de desarrollo SIN Docker.
#
# `start-codespace.sh` levanta la pila con docker compose, que es lo
# cómodo cuando hay demonio de Docker. No siempre lo hay: en un entorno
# de agente en la nube, en una VM sin privilegios o en un portátil
# corporativo con Docker bloqueado, no existe el socket y ese script no
# sirve. Sin una alternativa, en esos entornos la única verificación
# posible es `next build` y la suite sobre SQLite — se compila, pero
# nadie llega a USAR la aplicación, y hay fallos que solo aparecen al
# usarla.
#
# Este script levanta lo mismo con los servicios instalados en la
# máquina:
#
#   1. PostgreSQL local (arranca el clúster, crea rol y base).
#   2. Migraciones y catálogos sembrados.
#   3. Usuario administrador de demostración.
#   4. Django en :8000 y Next.js en :3000.
#
# Uso:   bash scripts/start-local.sh            # arranca
#        bash scripts/start-local.sh --stop     # para los servidores
#        bash scripts/start-local.sh --semilla  # añade datos de ejemplo
#
# Es idempotente: se puede correr las veces que haga falta.
#
# IMPORTANTE sobre el origen: el navegador debe entrar por
# http://localhost:3000, NO por http://127.0.0.1:3000. Para CORS son
# orígenes distintos y `CORS_ALLOWED_ORIGINS` solo trae localhost, así
# que desde 127.0.0.1 el login falla sin decir por qué: la petición se
# rechaza en el navegador y la pantalla se queda como estaba.

set -euo pipefail

cd "$(dirname "$0")/.."
RAIZ="$PWD"
EJECUCION="${TMPDIR:-/tmp}/clinica-dev"
mkdir -p "$EJECUCION"

# Credenciales de DESARROLLO. No sirven para producción y no deben
# copiarse a un .env real: la clave está a la vista en este archivo.
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export POSTGRES_DB=${POSTGRES_DB:-clinica}
export POSTGRES_USER=${POSTGRES_USER:-clinica}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-clinica}
export DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY:-dev-only-key-long-enough-for-hmac-validation-0123456789}
export DJANGO_DEBUG=True
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver

ADMIN_EMAIL=${ADMIN_EMAIL:-admin@demo.ec}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-demo12345}

parar() {
    echo "▶ Parando servidores…"
    for archivo in "$EJECUCION"/django.pid "$EJECUCION"/next.pid; do
        [ -f "$archivo" ] || continue
        pid=$(cat "$archivo")
        # Se mata el GRUPO de procesos: `next dev` lanza hijos y matar
        # solo al padre deja el puerto 3000 ocupado.
        kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
        rm -f "$archivo"
    done
    echo "✓ Servidores parados (PostgreSQL sigue en pie)."
}

if [ "${1:-}" = "--stop" ]; then
    parar
    exit 0
fi

# ── 1. PostgreSQL ────────────────────────────────────────────────────
echo "▶ PostgreSQL…"
if ! (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
    if command -v pg_ctlcluster >/dev/null 2>&1; then
        version=$(ls /usr/lib/postgresql | sort -rn | head -1)
        pg_ctlcluster "$version" main start 2>/dev/null || true
    else
        service postgresql start >/dev/null 2>&1 || true
    fi
fi
if ! (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; then
    echo "✗ No se pudo arrancar PostgreSQL. Instálalo o levántalo a mano." >&2
    exit 1
fi

# `su postgres` necesita raíz; si no la hay se asume que el rol ya existe.
if [ "$(id -u)" = "0" ]; then
    su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'\"" \
        | grep -q 1 \
        || su postgres -c "psql -q -c \"CREATE ROLE $POSTGRES_USER LOGIN PASSWORD '$POSTGRES_PASSWORD' SUPERUSER;\""
    su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'\"" \
        | grep -q 1 \
        || su postgres -c "createdb -O $POSTGRES_USER $POSTGRES_DB"
fi
echo "✓ PostgreSQL en 127.0.0.1:5432, base '$POSTGRES_DB'."

# ── 2. Migraciones y catálogos ───────────────────────────────────────
echo "▶ Migraciones y catálogos…"
cd "$RAIZ/django-api"
python3 manage.py migrate --no-input >/dev/null
python3 manage.py bootstrap >/dev/null
echo "✓ Esquema al día y catálogos sembrados."

# ── 3. Usuario administrador ─────────────────────────────────────────
ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" python3 - <<'PY'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.accounts.models import User          # noqa: E402
from apps.common.models import Tenant          # noqa: E402

tenant = Tenant.objects.first()
correo = os.environ["ADMIN_EMAIL"]
usuario, _ = User.objects.get_or_create(
    email=correo, defaults={"full_name": "Administración (demo)"}
)
usuario.role, usuario.tenant = "admin", tenant
usuario.set_password(os.environ["ADMIN_PASSWORD"])
usuario.save()
print(f"✓ Administrador: {correo} / {os.environ['ADMIN_PASSWORD']} — clínica «{tenant.name}»")
PY

# ── 4. Datos de ejemplo (opcional) ───────────────────────────────────
if [ "${1:-}" = "--semilla" ]; then
    python3 - <<'PY'
import os
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.common.models import Tenant                              # noqa: E402
from apps.configuration.models import Agreement, Tariff, Treatment  # noqa: E402
from apps.patients.models import Patient                            # noqa: E402
from apps.specialties.models import Specialty                       # noqa: E402

tenant = Tenant.objects.first()
especialidades = list(Specialty.objects.filter(tenant=tenant))

catalogo = [
    ("Profilaxis dental", "35.00"), ("Resina simple", "45.00"),
    ("Resina compuesta", "60.00"), ("Endodoncia unirradicular", "180.00"),
    ("Corona de zirconio", "400.00"), ("Extracción simple", "50.00"),
    ("Blanqueamiento", "220.00"),
]
for i, (nombre, precio) in enumerate(catalogo):
    Treatment.objects.get_or_create(
        tenant=tenant, name=nombre,
        defaults={"specialty": especialidades[i % len(especialidades)],
                  "base_price": Decimal(precio)},
    )

# Los tres casos que cubre la resolución de precios: convenio con
# porcentaje, convenio con tarifa pactada y convenio sin descuento.
seguro, _ = Agreement.objects.get_or_create(
    tenant=tenant, name="Seguros Equinoccial",
    defaults={"discount_percentage": Decimal("15.00")})
empresa, _ = Agreement.objects.get_or_create(
    tenant=tenant, name="Convenio Empresa Andina",
    defaults={"discount_percentage": Decimal("10.00")})
Agreement.objects.get_or_create(tenant=tenant, name="BMI Salud")

corona = Treatment.objects.get(tenant=tenant, name="Corona de zirconio")
Tariff.objects.get_or_create(tenant=tenant, treatment=corona, agreement=seguro,
                             defaults={"price": Decimal("260.00")})
resina = Treatment.objects.get(tenant=tenant, name="Resina simple")
Tariff.objects.get_or_create(tenant=tenant, treatment=resina, agreement=None,
                             defaults={"price": Decimal("40.00")})

for datos in [
    {"first_name": "Ana", "last_name": "Pérez Vela", "national_id": "0102030405",
     "agreement": seguro},
    {"first_name": "Luis", "last_name": "Mora Cedeño", "national_id": "0102030406",
     "agreement": empresa},
    {"first_name": "Sofía", "last_name": "Andrade Rojas", "national_id": "0102030407"},
]:
    Patient.objects.get_or_create(
        tenant=tenant, national_id=datos.pop("national_id"), defaults=datos)

print(f"✓ Semilla: {Treatment.objects.filter(tenant=tenant).count()} tratamientos, "
      f"{Agreement.objects.filter(tenant=tenant).count()} convenios, "
      f"{Patient.objects.filter(tenant=tenant).count()} pacientes.")
PY
fi

# ── 5. Servidores ────────────────────────────────────────────────────
parar 2>/dev/null || true

echo "▶ Levantando servidores…"
cd "$RAIZ/django-api"
setsid python3 manage.py runserver 127.0.0.1:8000 \
    > "$EJECUCION/django.log" 2>&1 < /dev/null &
echo $! > "$EJECUCION/django.pid"

cd "$RAIZ/frontend"
[ -d node_modules ] || npm ci --no-audit --no-fund
# La URL de la API se fija a localhost a propósito: ver la nota sobre
# CORS en la cabecera de este archivo.
setsid env NEXT_PUBLIC_API_URL=http://localhost:8000 npx next dev -p 3000 \
    > "$EJECUCION/next.log" 2>&1 < /dev/null &
echo $! > "$EJECUCION/next.pid"

esperar() {
    local url=$1 nombre=$2 intentos=0
    until curl -sf -o /dev/null "$url" 2>/dev/null; do
        intentos=$((intentos + 1))
        [ "$intentos" -gt 90 ] && { echo "✗ $nombre no respondió." >&2; return 1; }
        sleep 1
    done
    echo "✓ $nombre listo."
}
# /ready/ y no /health/: interesa esperar a que Django pueda ATENDER
# (base de datos incluida), no solo a que el proceso esté arriba.
esperar "http://localhost:8000/api/v1/ready/" "Django"
esperar "http://localhost:3000/login" "Next.js"

cat <<FIN

  Panel:     http://localhost:3000       (entra por localhost, no por 127.0.0.1)
  API:       http://localhost:8000/api/v1/
  Acceso:    $ADMIN_EMAIL / $ADMIN_PASSWORD

  Registros: $EJECUCION/django.log
             $EJECUCION/next.log
  Parar:     bash scripts/start-local.sh --stop
FIN
