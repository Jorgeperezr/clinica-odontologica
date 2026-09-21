# App del paciente

Aplicación Flutter para Android y iOS. Consume `apps/app_paciente` de la
API (Sprint 89): las citas del paciente, lo que debe y las indicaciones
que su profesional marcó como visibles.

Lo que **no** enseña, y es deliberado: odontograma, notas clínicas
internas, diagnósticos sin revisar, costes internos de los tratamientos
y cualquier dato de otro paciente. La app es una ventana para que el
paciente se organice, no una copia de su historia clínica.

## Cómo se entra

Por teléfono y código de WhatsApp (`/auth/otp/request/` y
`/auth/otp/verify/`), sin contraseña. Un paciente abre esta app dos
veces al año, y una contraseña que se usa dos veces al año es una
contraseña olvidada o apuntada en un papel.

## Ejecutar

El SDK de Flutter no viene con el repositorio. Con Flutter 3.47 o
posterior instalado:

```sh
cd movil
flutter pub get
flutter run --dart-define=API_URL=http://10.0.2.2      # emulador Android
flutter run --dart-define=API_URL=http://localhost     # simulador iOS
```

`API_URL` se pasa al compilar y no está escrita a fuego en el código.
En el emulador de Android, `10.0.2.2` es la máquina que lo hospeda; en
un dispositivo real hay que pasar la dirección de verdad.

```sh
flutter build apk   --dart-define=API_URL=https://clinica.ejemplo.ec
flutter build ipa   --dart-define=API_URL=https://clinica.ejemplo.ec
```

**La compilación necesita un Mac para iOS** (Xcode). Android se puede
compilar desde Linux o Mac.

## Validar

```sh
flutter analyze   # debe salir «No issues found!»
flutter test
```

## Cómo están escritas las pruebas

`test/fixtures/` **no está escrito a mano**: son respuestas capturadas
contra la API en marcha, entrando por el mismo OTP que usa la app. Por
eso las pruebas valen para algo: comprueban el contrato real y no el que
alguien recuerde. Si se renombra un campo en
`apps/app_paciente/views.py`, `flutter test` se pone rojo aquí en vez de
que un paciente vea un hueco en blanco en su teléfono.

Para volver a capturarlas, con la API levantada y un paciente con datos:

```sh
TOK=…   # el `access` que devuelve /auth/otp/verify/
for r in me citas saldo indicaciones; do
  curl -s -H "Authorization: Bearer $TOK" \
    "http://localhost/api/v1/app/$r/" -o "test/fixtures/$r.json"
done
```

## Decisiones que conviene no deshacer

- **El dinero se queda como cadena** de punta a punta. Llega como
  `"120.00"` desde un `Decimal` de Python y se pinta tal cual. Pasarlo a
  `double` para volver a mostrarlo es como aparecen las facturas que no
  cuadran por un centavo.
- **Los estados los traduce el servidor** («Confirmada», «Completada»).
  La app no mantiene su propia tabla, que se desincronizaría en cuanto
  el backend añadiera un estado.
- **La mora la decide el servidor**, comparando con la fecha de la
  clínica y no con la del teléfono. Alguien de viaje en otro huso no
  debe ver una cuota vencida un día antes de estarlo.
- **`vence` no lleva `toLocal()`**. Es una fecha suelta, sin hora ni
  huso; convertirla la correría un día en Ecuador (UTC−5).
- **Los tokens van al Keychain/Keystore**, no a `shared_preferences`,
  que es un XML legible en un teléfono con root. Dan acceso a datos
  clínicos.
- **El refresco es único y compartido.** El backend rota el `refresh` en
  cada uso (`ROTATE_REFRESH_TOKENS`); si cada petición pidiera el suyo,
  la primera invalidaría el de las demás y la sesión se caería sola
  nada más abrir la app. Hay una prueba que lo fija.
