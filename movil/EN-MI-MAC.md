# Ejecutar la app del paciente en el Mac

> **Sobre los comandos de este documento:** ninguno lleva comentarios
> pegados detrás. En zsh, que es el intérprete de macOS, la opción
> `interactive_comments` puede estar desactivada, y entonces el `#` y lo
> que le sigue **llegan como argumentos** al programa. Así falló
> `xcode-select --install # herramientas…` con `invalid argument '#'`.
> Es el mismo tipo de fallo que el `?` de `openssl version # ¿LibreSSL?`,
> que zsh intentó expandir como comodín. Los comentarios van arriba,
> nunca en la misma línea.

---

## Lo más rápido: verla en Chrome

Si lo que quieres es **ver la app funcionando ya**, no hace falta Xcode
ni Android Studio. Dos terminales y está:

```sh
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5000 bash scripts/start-local.sh
```

```sh
bash scripts/movil.sh --web
```

Abre Chrome en el 5000 contra la API del 8000.

**Para qué sirve y para qué no.** Sirve para ver las pantallas, el flujo
de ingreso y que los datos lleguen bien. No sirve para entregar: en web
los tokens acaban en el almacenamiento del navegador y no en el Keychain
del teléfono, que es lo que protege datos clínicos. Para eso, iOS o
Android de verdad.

---

## iOS

### 1. Xcode completo

Las *Command Line Tools* **no bastan**. `xcodebuild` necesita Xcode
entero, y sin él sale:

```
xcode-select: error: tool 'xcodebuild' requires Xcode, but active
developer directory '/Library/Developer/CommandLineTools' is a command
line tools instance
```

Instala Xcode desde la App Store. Son más de 10 GB, así que déjalo
descargando y sigue con otra cosa.

**Sobre tu Mac:** es Intel x86_64, y Homebrew ya avisa de que Apple dejó
esa arquitectura fuera en macOS 27. Xcode sigue funcionando en Intel hoy,
pero la App Store solo te ofrecerá la última versión compatible con tu
macOS. Si Xcode no te deja instalarlo, el camino de Chrome de arriba y el
de Android siguen abiertos.

### 2. Solo cuando Xcode ya esté instalado

Estas tres líneas van **después**, no antes. Ese fue el orden equivocado
de la versión anterior de este documento:

```sh
sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -runFirstLaunch
sudo gem install cocoapods
```

La primera apunta las herramientas a Xcode en vez de a las Command Line
Tools, que es justo lo que faltaba.

### 3. Arrancar

```sh
open -a Simulator
bash scripts/movil.sh
```

---

## Android

No necesita Xcode. Android Studio desde
<https://developer.android.com/studio>; dentro, *More Actions → SDK
Manager*, y luego *Device Manager* para crear un emulador y arrancarlo.

```sh
bash scripts/movil.sh
```

---

## Comprobar antes de intentar

```sh
bash scripts/movil.sh --comprobar
```

Revisa el SDK, los destinos disponibles, si la API responde y qué URL le
corresponde a cada destino. No arranca nada: solo dice qué falta. Con
`--web` comprueba además que CORS deje pasar al navegador.

Si el problema es de Python o PostgreSQL, el diagnóstico de eso está en
`bash scripts/comprobar-entorno.sh`.

---

## La URL: lo único que no se adivina

Equivocarse aquí da un error de red que parece un fallo de la app:

| Destino | URL | Por qué |
|---|---|---|
| Chrome | `http://localhost:8000` | Es el propio Mac, pero Chrome exige CORS |
| Simulador de iOS | `http://localhost:8000` | Comparte la red del Mac |
| Emulador de Android | `http://10.0.2.2:8000` | Dentro del emulador, `10.0.2.2` **es** el Mac |
| Teléfono real | `http://<IP-del-Mac>:8000` | Va por la wifi |

`scripts/movil.sh` elige la correcta. A mano:

```sh
cd movil
flutter run --dart-define=API_URL=http://localhost:8000
```

```sh
cd movil
flutter run --dart-define=API_URL=http://10.0.2.2:8000
```

### Con un teléfono de verdad

```sh
ipconfig getifaddr en0
```

Devuelve la IP del Mac en la wifi. Hacen falta dos cosas más, y las dos
dan errores que despistan:

**1. Que Django acepte esa IP**, o responde `DisallowedHost`:

```sh
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2,192.168.1.40
```

**2. Que Django escuche fuera de `localhost`.** `start-local.sh` lo
levanta en `127.0.0.1:8000`, que un teléfono no alcanza:

```sh
cd django-api
python manage.py runserver 0.0.0.0:8000
```

Y el guion con esa IP:

```sh
bash scripts/movil.sh --ip 192.168.1.40
```

---

## Entrar en la app

El paciente entra **por teléfono y código de WhatsApp**, sin contraseña.
En local no hay gateway de WhatsApp levantado, así que el código no llega
a ningún sitio: se lee de la base.

Crear un paciente de prueba:

```sh
cd django-api
python manage.py shell -c "
from apps.accounts.models import User
from apps.common.models import Tenant
t = Tenant.objects.first()
u, _ = User.objects.get_or_create(phone='+593999111222',
        defaults={'role':'patient','full_name':'Ana Prueba','tenant':t})
u.role='patient'; u.tenant=t; u.is_active=True; u.save()
print('listo:', u.phone)
"
```

Pide el código desde la app y luego léelo:

```sh
cd django-api
python manage.py shell -c "
from apps.accounts.models import OTPCode, User
from apps.accounts.views import _hash_value
u = User.objects.get(phone='+593999111222')
o = OTPCode.objects.filter(user=u, used_at__isnull=True).order_by('-created_at').first()
print(next(f'{i:06d}' for i in range(1000000) if _hash_value(f'{i:06d}')==o.code_hash))
"
```

Se guarda hasheado, así que se prueban los seis dígitos hasta dar con él.
Tarda un par de segundos y solo sirve en desarrollo.

Para que la app enseñe algo, ese paciente necesita citas, cuotas o
indicaciones: créalas desde el panel en `http://localhost:3000` con la
cuenta de la clínica.

---

## Compilar para entregar

```sh
cd movil
flutter build apk --dart-define=API_URL=https://tu-dominio.ec
```

```sh
cd movil
flutter build ipa --dart-define=API_URL=https://tu-dominio.ec
```

`API_URL` se pasa **al compilar**: no está escrita en el código, así que
el mismo repositorio sirve para desarrollo y para producción sin tocar
nada.

---

## Si algo falla

| Lo que ves | Qué pasa |
|---|---|
| `invalid argument '#'` | Copiaste un comando con un comentario detrás; zsh no lo trata como tal |
| `xcodebuild requires Xcode` | Solo tienes las Command Line Tools; falta Xcode completo |
| `DisallowedHost` en el log de Django | La URL que usa la app no está en `DJANGO_ALLOWED_HOSTS` |
| La app se queda cargando y en Chrome la consola habla de CORS | Falta el 5000 en `CORS_ALLOWED_ORIGINS` |
| «No se pudo contactar con la clínica» | La API no está levantada, o es la URL equivocada para ese destino |
| `CocoaPods not installed` | `sudo gem install cocoapods` y repite |
| La app abre en una ventana de escritorio | No había simulador y Flutter eligió macOS; abre uno y repite |
