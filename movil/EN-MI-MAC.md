# Ejecutar la app del paciente en el Mac

Todo lo de abajo se hace **una vez**. Después, cada sesión son dos
terminales: la API en una y `scripts/movil.sh` en la otra.

> Atajo: si ya tienes Flutter y Xcode, salta al paso 4 y ejecuta
> `bash scripts/movil.sh --comprobar`. Te dirá exactamente qué falta.

---

## 1. Flutter

```sh
brew install --cask flutter
flutter --version        # debe decir 3.47.5 o posterior
```

El CI fija **3.47.5**. Con una versión anterior puede no compilar, y con
una mucho más nueva `flutter analyze` puede sacar avisos nuevos sin que
nadie haya tocado el código — es lo mismo que nos pasó con `ruff`.

## 2. Xcode, para iOS

```sh
xcode-select --install                  # herramientas de línea de comandos
sudo xcodebuild -runFirstLaunch         # acepta la licencia
sudo gem install cocoapods              # dependencias nativas de iOS
```

Xcode completo se instala desde la App Store. **Es obligatorio para
iOS**; no hay forma de compilar para iPhone sin un Mac.

## 3. Android Studio, para Android (opcional)

Desde <https://developer.android.com/studio>. Dentro: *More Actions →
SDK Manager* y luego *Device Manager* para crear un emulador.

## 4. Comprobar antes de intentar

```sh
cd ~/ruta/al/clinica-odontologica
bash scripts/movil.sh --comprobar
```

Revisa el SDK, los destinos disponibles, si la API responde y qué URL
le corresponde a cada destino. No arranca nada: solo dice qué falta.

Si algo se queja del entorno de Python o PostgreSQL, el diagnóstico
completo de eso está en `bash scripts/comprobar-entorno.sh`.

## 5. Arrancar

**Terminal 1 — la API:**

```sh
bash scripts/start-local.sh
```

Levanta PostgreSQL, Django en el **8000** y el panel en el 3000.

**Terminal 2 — un simulador y la app:**

```sh
open -a Simulator          # iOS; para Android, el Device Manager
bash scripts/movil.sh
```

El guion resuelve dependencias, pasa el análisis, ejecuta las pruebas y
solo entonces arranca. Si las pruebas están en rojo se detiene: arrancar
con el contrato roto confunde más de lo que ayuda.

---

## La URL: lo único que no se adivina

No es la misma desde cada destino, y equivocarse aquí da un error de red
que parece un fallo de la app:

| Destino | URL | Por qué |
|---|---|---|
| Simulador de iOS | `http://localhost:8000` | Comparte la red del Mac |
| Emulador de Android | `http://10.0.2.2:8000` | Dentro del emulador, `10.0.2.2` **es** el Mac |
| iPhone o Android real | `http://<IP-del-Mac>:8000` | Va por la wifi |

`scripts/movil.sh` elige la correcta cuando solo hay un destino. A mano:

```sh
cd movil
flutter run --dart-define=API_URL=http://localhost:8000    # iOS
flutter run --dart-define=API_URL=http://10.0.2.2:8000     # Android
```

### Con un teléfono de verdad

Dos cosas más, y las dos dan errores que despistan:

```sh
ipconfig getifaddr en0        # la IP del Mac en la wifi, p. ej. 192.168.1.40
```

1. **Django tiene que aceptar esa IP**, o responde `DisallowedHost`:

   ```sh
   export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,10.0.2.2,192.168.1.40
   ```

2. **Django tiene que escuchar fuera de `localhost`.** `start-local.sh`
   lo levanta en `127.0.0.1:8000`, que un teléfono no alcanza:

   ```sh
   cd django-api && python manage.py runserver 0.0.0.0:8000
   ```

Y el guion con la IP:

```sh
bash scripts/movil.sh --ip 192.168.1.40
```

---

## Entrar en la app

El paciente entra **por teléfono y código de WhatsApp**, sin contraseña.
En local no hay gateway de WhatsApp levantado, así que el código no
llega a ningún sitio: se lee de la base.

Necesitas un usuario con rol `patient` y teléfono. Para crear uno de
prueba y sacar su código:

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

Se guarda hasheado, así que se prueban los seis dígitos hasta dar con
él. Tarda un par de segundos y solo sirve en desarrollo.

Para que la app enseñe algo, ese paciente necesita citas, cuotas o
indicaciones: créalas desde el panel (`http://localhost:3000`) con la
cuenta de la clínica.

---

## Compilar para entregar

```sh
cd movil
flutter build apk --dart-define=API_URL=https://tu-dominio.ec   # Android
flutter build ipa --dart-define=API_URL=https://tu-dominio.ec   # iOS
```

`API_URL` se pasa **al compilar**: no está escrita en el código, así que
el mismo repositorio sirve para desarrollo y para producción sin tocar
nada.

---

## Si algo falla

| Lo que ves | Qué pasa |
|---|---|
| `DisallowedHost` en el log de Django | La URL que usa la app no está en `DJANGO_ALLOWED_HOSTS` |
| «No se pudo contactar con la clínica» | La API no está levantada, o es la URL equivocada para ese destino |
| `CocoaPods not installed` | `sudo gem install cocoapods` y repite |
| `flutter analyze` saca avisos que aquí no salían | Tu Flutter es más nuevo que el 3.47.5 del CI |
| La app abre en una ventana de escritorio | No había simulador y Flutter eligió macOS; abre uno y repite |
