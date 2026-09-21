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
#   0. Intérprete compatible y entorno virtual con las dependencias.
#   1. PostgreSQL local (arranca el clúster, crea rol y base).
#   2. Migraciones y catálogos sembrados.
#   3. Usuario administrador de demostración.
#   4. Django en :8000 y Next.js en :3000.
#
# Funciona en Linux y en macOS. Las tres cosas que lo impedían en macOS
# estaban aquí, no en la máquina de nadie:
#
#   · Llamaba a `python3` a secas. En un Mac al día eso es 3.14, y
#     Django 5.0 declara soporte hasta 3.12. El paquete se instala
#     igual —`Requires-Python: >=3.10` no pone techo— y luego falla por
#     su cuenta, lejos de la causa.
#   · No instalaba las dependencias en ninguna parte: daba por hecho un
#     Django ya presente. En un clon recién hecho eso es
#     `ModuleNotFoundError: No module named django`.
#   · Arrancaba PostgreSQL con `pg_ctlcluster` y creaba el rol con
#     `su postgres`: las dos cosas son de Linux y la segunda pedía raíz.
#     En macOS no se creaba el rol y `migrate` moría con «role "clinica"
#     does not exist», que tampoco se parece a la causa.
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
# 10.0.2.2 es la máquina anfitriona VISTA DESDE el emulador de Android,
# y llega en la cabecera Host. Sin esto Django responde DisallowedHost
# y la app móvil no puede ni iniciar sesión. El simulador de iOS usa
# `localhost`, así que ese caso ya estaba cubierto por casualidad.
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver,10.0.2.2
# El panel va en el 3000 y la app del paciente en Chrome (`flutter run -d
# chrome --web-port=5000`) en el 5000. Sin el 5000 aquí, Django responde
# 200 pero SIN la cabecera `access-control-allow-origin` y el navegador
# bloquea cada petición: la app se queda cargando y el motivo solo se ve
# en la consola del navegador. Medido con un preflight, no supuesto.
export CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5000

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

# ── 0. Intérprete y entorno virtual ──────────────────────────────────
echo "▶ Python…"

# Se busca un intérprete que Django 5.0 declare soportado (3.10 a 3.12)
# ANTES de mirar el de por defecto, que en un Mac al día es más nuevo de
# lo que nadie ha probado. La lista se puede sobrescribir para pyenv o
# asdf, donde los intérpretes tienen otro nombre.
INTERPRETE=""
for cmd in ${PY_CANDIDATOS:-python3.12 python3.11 python3.10}; do
    if command -v "$cmd" >/dev/null 2>&1; then
        INTERPRETE="$cmd"
        break
    fi
done

if [ -z "$INTERPRETE" ]; then
    # No hay ninguno con nombre de versión. Se acepta el de por defecto
    # solo si cae dentro del rango; fuera de él se para aquí, que es
    # mucho mejor que fallar dentro de Django media hora después.
    if command -v python3 >/dev/null 2>&1 && python3 -c \
            'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)' \
            2>/dev/null; then
        INTERPRETE="python3"
    else
        VISTO=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null \
                || echo "ninguno")
        cat >&2 <<FIN
✗ No hay un Python compatible. Visto: $VISTO
  Django 5.0 soporta 3.10, 3.11 y 3.12; el CI y el contenedor usan 3.12.

  macOS:  brew install python@3.12
  Linux:  apt install python3.12-venv

  No hace falta desinstalar el que tengas: conviven y este guion elige.
FIN
        exit 1
    fi
fi

VENV="$RAIZ/.venv"
if [ ! -x "$VENV/bin/python" ]; then
    echo "  Creando entorno virtual con ${INTERPRETE}…"
    "$INTERPRETE" -m venv "$VENV"
fi
PY="$VENV/bin/python"

# En macOS el pip de Homebrew se niega a instalar fuera de un entorno
# virtual (PEP 668, «externally-managed-environment»), así que el venv
# no es una comodidad: es la única forma de que esto funcione.
#
# Se reinstala cuando requirements.txt cambia, y para saberlo se guarda
# su suma junto al entorno. `cksum` y no `sha256sum` porque en macOS ese
# comando no existe; aquí se trata de notar una edición, no de resistir
# a nadie.
SUMA_ACTUAL=$(cksum "$RAIZ/django-api/requirements.txt" | awk '{print $1, $2}')
MARCA="$VENV/.requirements.cksum"
if [ ! -f "$MARCA" ] || [ "$(cat "$MARCA")" != "$SUMA_ACTUAL" ]; then
    echo "  Instalando dependencias (la primera vez tarda)…"
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -r "$RAIZ/django-api/requirements.txt"
    echo "$SUMA_ACTUAL" > "$MARCA"
fi
echo "✓ $("$PY" -V) en .venv, dependencias al día."

# ── 1. PostgreSQL ────────────────────────────────────────────────────
echo "▶ PostgreSQL…"

escuchando() { (echo > /dev/tcp/127.0.0.1/5432) >/dev/null 2>&1; }

if ! escuchando; then
    if command -v pg_ctlcluster >/dev/null 2>&1; then
        version=$(ls /usr/lib/postgresql | sort -rn | head -1)
        pg_ctlcluster "$version" main start 2>/dev/null || true
    elif command -v brew >/dev/null 2>&1; then
        # macOS con Homebrew. El servicio se llama distinto según cómo se
        # instalara, así que se prueban los nombres habituales en vez de
        # dar por supuesto uno.
        for servicio in postgresql@16 postgresql@15 postgresql@14 postgresql; do
            if brew services list 2>/dev/null | grep -q "^$servicio "; then
                echo "  Arrancando ${servicio}…"
                brew services start "$servicio" >/dev/null 2>&1 || true
                break
            fi
        done
        # `brew services` devuelve antes de que el servidor acepte
        # conexiones; sin esta espera el primer psql falla y parecería
        # que no hay PostgreSQL.
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            escuchando && break
            sleep 1
        done
    else
        service postgresql start >/dev/null 2>&1 || true
    fi
fi

if ! escuchando; then
    cat >&2 <<FIN
✗ No se pudo arrancar PostgreSQL en 127.0.0.1:5432.

  macOS:  brew install postgresql@16 && brew services start postgresql@16
  Linux:  sudo service postgresql start
FIN
    exit 1
fi

# Creación del rol y la base. Dos caminos, porque las dos instalaciones
# habituales no se parecen en nada:
#
#   · Linux/Debian: los datos son del usuario del sistema `postgres` y
#     hay que pasar por él, lo que exige raíz.
#   · macOS/Homebrew: no existe ese usuario del sistema; quien instaló
#     es ya superusuario de la base y se conecta directamente.
crear_rol_y_base() {
    local ejecutar="$1"
    $ejecutar "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'" | grep -q 1 \
        || $ejecutar "CREATE ROLE $POSTGRES_USER LOGIN PASSWORD '$POSTGRES_PASSWORD' SUPERUSER" >/dev/null
    $ejecutar "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | grep -q 1 \
        || $ejecutar "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER" >/dev/null
}

como_postgres() { su postgres -c "psql -tAc \"$1\""; }
como_yo()       { psql -d postgres -tAc "$1"; }

if [ "$(id -u)" = "0" ] && id postgres >/dev/null 2>&1; then
    crear_rol_y_base como_postgres
elif psql -d postgres -tAc "SELECT 1" >/dev/null 2>&1; then
    crear_rol_y_base como_yo
elif PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" -tAc "SELECT 1" >/dev/null 2>&1; then
    # El rol y la base ya existen y funcionan: no hay nada que crear.
    :
else
    cat >&2 <<FIN
✗ PostgreSQL responde, pero no se pudo crear el rol «${POSTGRES_USER}».

  No hay forma de conectarse como superusuario: ni como root por el
  usuario del sistema «postgres» (Linux) ni directamente (macOS).

  Créalos a mano y vuelve a lanzar esto:
    psql -d postgres -c "CREATE ROLE $POSTGRES_USER LOGIN PASSWORD '$POSTGRES_PASSWORD' SUPERUSER;"
    psql -d postgres -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"
FIN
    exit 1
fi
echo "✓ PostgreSQL en 127.0.0.1:5432, base '$POSTGRES_DB'."

# ── 2. Migraciones y catálogos ───────────────────────────────────────
echo "▶ Migraciones y catálogos…"
cd "$RAIZ/django-api"
"$PY" manage.py migrate --no-input >/dev/null
"$PY" manage.py bootstrap >/dev/null
echo "✓ Esquema al día y catálogos sembrados."

# ── 3. Usuario administrador ─────────────────────────────────────────
ADMIN_EMAIL="$ADMIN_EMAIL" ADMIN_PASSWORD="$ADMIN_PASSWORD" "$PY" - <<'FIN_PY'
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

# Un doctor con su ficha. Sin al menos uno, el desplegable «Doctor» del
# formulario de cita está vacío y NO se puede agendar nada: el módulo de
# agenda entero queda fuera de alcance en un entorno recién levantado.
from apps.agenda.models import Doctor                # noqa: E402

doctora, _ = User.objects.get_or_create(
    email="doctora@demo.ec",
    defaults={"full_name": "Dra. Valeria Núñez"},
)
doctora.role, doctora.tenant = "doctor", tenant
doctora.set_password(os.environ["ADMIN_PASSWORD"])
doctora.save()
ficha, _ = Doctor.objects.get_or_create(tenant=tenant, user=doctora)
if not ficha.license_number:
    ficha.license_number = "MSP-00123"
    ficha.save(update_fields=["license_number"])
print(f"✓ Doctora: {doctora.email} / {os.environ['ADMIN_PASSWORD']}")
FIN_PY

# ── 4. Datos de ejemplo (opcional) ───────────────────────────────────
if [ "${1:-}" = "--semilla" ]; then
    "$PY" - <<'FIN_PY'
import os
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.common.models import Tenant                              # noqa: E402
from apps.clinical.models import (                                   # noqa: E402
    TreatmentPlanTemplate, TreatmentPlanTemplateItem,
)
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

# Plantillas de plan. Sin al menos una, la pestaña «Plan de tratamiento»
# de la ficha NO deja crear nada: su único control es «Crear plan desde
# plantilla», y con el desplegable vacío no hay camino. Y sin plan no hay
# presupuesto, ni cuotas, ni cobro: la ruta del dinero entera queda fuera
# de alcance. Se siembran dos para poder recorrerla.
protocolos = [
    ("Rehabilitación básica", ["Profilaxis dental", "Resina simple", "Resina compuesta"]),
    ("Corona sobre endodoncia", ["Endodoncia unirradicular", "Corona de zirconio"]),
]
for nombre, pasos in protocolos:
    plantilla, _ = TreatmentPlanTemplate.objects.get_or_create(
        tenant=tenant, name=nombre,
        defaults={"description": "Protocolo de ejemplo para desarrollo."},
    )
    for orden, tratamiento in enumerate(pasos, start=1):
        TreatmentPlanTemplateItem.objects.get_or_create(
            template=plantilla,
            treatment=Treatment.objects.get(tenant=tenant, name=tratamiento),
            defaults={"order": orden},
        )

print(f"✓ Semilla: {Treatment.objects.filter(tenant=tenant).count()} tratamientos, "
      f"{Agreement.objects.filter(tenant=tenant).count()} convenios, "
      f"{Patient.objects.filter(tenant=tenant).count()} pacientes, "
      f"{TreatmentPlanTemplate.objects.filter(tenant=tenant).count()} plantillas de plan.")
FIN_PY
fi

# ── 5. Servidores ────────────────────────────────────────────────────
parar 2>/dev/null || true

echo "▶ Levantando servidores…"

# Arranca un proceso en una sesión NUEVA, para poder matar después al
# grupo entero: `next dev` lanza hijos y matar solo al padre deja el
# puerto 3000 ocupado.
#
# Esto era `setsid`, que es de util-linux y **no existe en macOS**. Allí
# el proceso moría al instante con «command not found» dentro de un
# segundo plano —donde `set -e` no lo ve— y el guion se quedaba noventa
# segundos esperando a algo que ya no estaba, para terminar diciendo
# «Django no respondió» sin una sola pista más.
#
# Se hace con Python, que aquí ya hace falta y está en los dos sistemas:
# `os.setsid()` abre la sesión y `execvp` se convierte en el servidor, de
# modo que el PID que guardamos es el definitivo. Con `setsid` eso no
# siempre era cierto, porque bifurca si ya era líder del grupo.
# El `exec` y los paréntesis de quien la llama no son adorno: sin ellos
# bash bifurca una vez más y el PID que apunta `$!` es el de un
# intermediario que muere enseguida, no el del servidor. Entonces
# `kill -- -$pid` apunta a un grupo vacío y `--stop` deja los puertos
# ocupados diciendo que ha parado los servidores. Comprobado: sin `exec`,
# $! = 589 y el proceso real era el 591.
lanzar() {
    exec "$PY" -c 'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' "$@"
}

cd "$RAIZ/django-api"
( lanzar "$PY" manage.py runserver 127.0.0.1:8000 ) \
    > "$EJECUCION/django.log" 2>&1 < /dev/null &
echo $! > "$EJECUCION/django.pid"

cd "$RAIZ/frontend"
[ -d node_modules ] || npm ci --no-audit --no-fund
# La URL de la API se fija a localhost a propósito: ver la nota sobre
# CORS en la cabecera de este archivo.
# Se llama al binario de Next directamente y no por `npx`, que mete dos
# procesos de por medio —`npm exec` y un `sh -c`— sin aportar nada aquí:
# el paquete está instalado al lado. Menos intermediarios, menos sitios
# donde perder la pista al apagar.
( lanzar env NEXT_PUBLIC_API_URL=http://localhost:8000 \
    ./node_modules/.bin/next dev -p 3000 ) \
    > "$EJECUCION/next.log" 2>&1 < /dev/null &
echo $! > "$EJECUCION/next.pid"

esperar() {
    local url=$1 nombre=$2 registro=$3 pid=$4 intentos=0
    until curl -sf -o /dev/null "$url" 2>/dev/null; do
        # Si el proceso ya no está, no tiene sentido seguir esperando: se
        # murió al arrancar y la razón está en su registro. Antes esto
        # eran noventa segundos de silencio y un mensaje que no decía
        # nada; el motivo llevaba ahí desde el primer segundo.
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "✗ $nombre se cerró nada más arrancar." >&2
            explicar "$nombre" "$registro"
            return 1
        fi
        intentos=$((intentos + 1))
        if [ "$intentos" -gt 90 ]; then
            echo "✗ $nombre no respondió en 90 segundos." >&2
            explicar "$nombre" "$registro"
            return 1
        fi
        sleep 1
    done
    echo "✓ $nombre listo."
}

explicar() {
    local nombre=$1 registro=$2
    if [ -s "$registro" ]; then
        echo "  Últimas líneas de $registro:" >&2
        tail -25 "$registro" | sed 's/^/    /' >&2
    else
        echo "  Su registro ($registro) está vacío: no llegó ni a escribir." >&2
    fi
    echo "" >&2
    echo "  Cuando lo hayas corregido:  bash scripts/start-local.sh" >&2
}

# /ready/ y no /health/: interesa esperar a que Django pueda ATENDER
# (base de datos incluida), no solo a que el proceso esté arriba.
esperar "http://localhost:8000/api/v1/ready/" "Django" \
    "$EJECUCION/django.log" "$(cat "$EJECUCION/django.pid")"
esperar "http://localhost:3000/login" "Next.js" \
    "$EJECUCION/next.log" "$(cat "$EJECUCION/next.pid")"

cat <<FIN

  Panel:     http://localhost:3000       (entra por localhost, no por 127.0.0.1)
  API:       http://localhost:8000/api/v1/
  Acceso:    $ADMIN_EMAIL / $ADMIN_PASSWORD

  Registros: $EJECUCION/django.log
             $EJECUCION/next.log
  Parar:     bash scripts/start-local.sh --stop
FIN
