#!/usr/bin/env bash
#
# Arranca la app del paciente en un simulador o en un teléfono.
#
# Existe porque los tres fallos que se comen una tarde no están en el
# código de la app, sino alrededor: el SDK que falta, la API que no está
# levantada y —el más difícil de adivinar— la URL, que NO es la misma
# desde el simulador de iOS que desde el emulador de Android.
#
#   bash scripts/movil.sh              # elige destino y arranca
#   bash scripts/movil.sh --comprobar  # solo diagnostica, no arranca
#   bash scripts/movil.sh --ip 192.168.1.40   # teléfono real por wifi
#
# Las variables van SIEMPRE entre llaves —${VAR}— porque en macOS una
# variable pegada a un carácter no ASCII se traga esos bytes dentro del
# identificador. Ya nos pasó en los guiones de copia.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="${RAIZ}/movil"
PUERTO_API=8000

verde()  { printf '\033[0;32m✓\033[0m %s\n' "$1"; }
rojo()   { printf '\033[0;31m✗\033[0m %s\n' "$1"; }
aviso()  { printf '\033[0;33m!\033[0m %s\n' "$1"; }
titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }

SOLO_COMPROBAR=0
IP_MANUAL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --comprobar) SOLO_COMPROBAR=1; shift ;;
    --ip) IP_MANUAL="${2:-}"; shift 2 ;;
    *) rojo "Opción desconocida: $1"; exit 2 ;;
  esac
done

FALLOS=0

titulo "1. Dónde estamos"
if [ -d "${APP}/lib" ]; then
  verde "Proyecto encontrado en ${APP}"
else
  rojo "No encuentro ${APP}. ¿Estás en el repositorio clonado?"
  exit 1
fi

titulo "2. Flutter"
if command -v flutter >/dev/null 2>&1; then
  VERSION="$(flutter --version 2>/dev/null | head -1)"
  verde "${VERSION}"
  # El CI fija 3.47.5. Una versión muy distinta puede activar avisos
  # nuevos y hacer que `flutter analyze` falle sin que nadie toque el
  # código, igual que nos pasó con ruff 0.16.
  MAYOR="$(flutter --version 2>/dev/null | head -1 | sed -E 's/Flutter ([0-9]+)\.([0-9]+).*/\1\2/')"
  if [ -n "${MAYOR}" ] && [ "${MAYOR}" -lt 347 ] 2>/dev/null; then
    aviso "El CI usa Flutter 3.47.5. Con una anterior puede no compilar."
  fi
else
  rojo "Flutter no está instalado."
  echo "    brew install --cask flutter"
  echo "    …o https://docs.flutter.dev/get-started/install/macos"
  FALLOS=$((FALLOS+1))
fi

titulo "3. Destinos disponibles"
if command -v flutter >/dev/null 2>&1; then
  DISPOSITIVOS="$(flutter devices 2>/dev/null)"
  echo "${DISPOSITIVOS}" | sed 's/^/    /' | head -12
  HAY_IOS=0; HAY_ANDROID=0
  echo "${DISPOSITIVOS}" | grep -qi "ios"     && HAY_IOS=1
  echo "${DISPOSITIVOS}" | grep -qi "android" && HAY_ANDROID=1
  if [ "${HAY_IOS}" -eq 0 ] && [ "${HAY_ANDROID}" -eq 0 ]; then
    # Cuenta como fallo y no como aviso: en un Mac SIEMPRE aparecen
    # «macOS (desktop)» y «Chrome (web)», así que un resumen en verde
    # aquí haría creer que se puede arrancar, y `flutter run` fallaría
    # a continuación o abriría la app del paciente en una ventana de
    # escritorio, que no es lo que se quiere probar.
    rojo "No hay ningún simulador ni teléfono de iOS o Android."
    echo "    iOS:     open -a Simulator"
    echo "    Android: abre Android Studio → Device Manager → ▶"
    FALLOS=$((FALLOS+1))
  fi
fi

titulo "4. La API"
if curl -fsS --max-time 4 "http://localhost:${PUERTO_API}/api/v1/health/" >/dev/null 2>&1; then
  verde "Django responde en el ${PUERTO_API}."
else
  rojo "Django NO responde en http://localhost:${PUERTO_API}/"
  echo "    En otra terminal:  bash scripts/start-local.sh"
  FALLOS=$((FALLOS+1))
fi

titulo "5. La URL que verá la app"
# Esto es lo que nadie adivina a la primera:
#   · el simulador de iOS comparte la red del Mac  -> localhost
#   · el emulador de Android está "en otra máquina" -> 10.0.2.2
#   · un teléfono de verdad va por la wifi          -> IP del Mac
if [ -n "${IP_MANUAL}" ]; then
  URL="http://${IP_MANUAL}:${PUERTO_API}"
  echo "    Teléfono real por wifi -> ${URL}"
  aviso "Añade esa IP a DJANGO_ALLOWED_HOSTS o Django la rechazará:"
  echo "    export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2,${IP_MANUAL}"
else
  echo "    Simulador iOS      -> http://localhost:${PUERTO_API}"
  echo "    Emulador Android   -> http://10.0.2.2:${PUERTO_API}"
  echo "    (10.0.2.2 es este Mac visto desde dentro del emulador)"
  URL=""
fi

if [ "${FALLOS}" -gt 0 ]; then
  titulo "Resumen"
  rojo "${FALLOS} cosa(s) por resolver antes de arrancar."
  exit 1
fi

if [ "${SOLO_COMPROBAR}" -eq 1 ]; then
  titulo "Resumen"
  verde "Todo listo. Quita --comprobar para arrancar."
  exit 0
fi

titulo "6. Dependencias, análisis y pruebas"
cd "${APP}" || exit 1
flutter pub get >/dev/null 2>&1 && verde "Dependencias resueltas." \
  || { rojo "Falló 'flutter pub get'."; exit 1; }

if flutter analyze 2>&1 | tail -1 | grep -q "No issues found"; then
  verde "Análisis limpio."
else
  aviso "El análisis encontró avisos:"
  flutter analyze 2>&1 | tail -8 | sed 's/^/    /'
fi

if flutter test 2>&1 | tail -1 | grep -q "All tests passed"; then
  verde "Pruebas en verde."
else
  rojo "Hay pruebas en rojo. Arrancar igualmente puede confundir más que ayudar."
  flutter test 2>&1 | tail -12 | sed 's/^/    /'
  exit 1
fi

titulo "7. Arrancando"
if [ -z "${URL}" ]; then
  # Se deja que Flutter pregunte el destino y se elige la URL según lo
  # que haya: si solo hay iOS, localhost; si solo Android, 10.0.2.2.
  if [ "${HAY_IOS:-0}" -eq 1 ] && [ "${HAY_ANDROID:-0}" -eq 0 ]; then
    URL="http://localhost:${PUERTO_API}"
  elif [ "${HAY_ANDROID:-0}" -eq 1 ] && [ "${HAY_IOS:-0}" -eq 0 ]; then
    URL="http://10.0.2.2:${PUERTO_API}"
  else
    echo "    Hay varios destinos. Elige uno y, si es Android, vuelve con:"
    echo "      flutter run --dart-define=API_URL=http://10.0.2.2:${PUERTO_API}"
    URL="http://localhost:${PUERTO_API}"
  fi
fi
echo "    API_URL=${URL}"
echo
exec flutter run --dart-define=API_URL="${URL}"
