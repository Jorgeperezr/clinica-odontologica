# Guía de despliegue a producción

## Decisión de hosting (pendiente del usuario)

| Criterio | Opción A: VM en GCP | Opción B: PC en la clínica + Cloudflare Tunnel |
|---|---|---|
| Costo mensual | ~US$35-45 (e2-medium + disco + IP) | ~US$0 (electricidad + internet ya pagados) |
| Disponibilidad | Alta (99.9%; SLA del proveedor) | Depende de la luz/internet de la clínica |
| Acceso remoto | Nativo (IP pública) | Vía túnel (sin abrir puertos del router) |
| Backups | Snapshots automáticos del disco | Hay que armarlos (script pg_dump + copia externa) |
| Mantenimiento | Actualizaciones del SO a cargo tuyo | Ídem + hardware físico a tu cargo |
| Riesgo principal | Costo recurrente | Robo/daño del equipo = pérdida del servidor |
| Recomendado si… | La clínica depende del sistema a diario | Presupuesto cero y tolerancia a caídas |

**Recomendación:** empezar con la Opción B (costo cero) durante la marcha
blanca, con backups externos diarios; migrar a la Opción A cuando el
sistema sea crítico para la operación. El código es idéntico en ambas.

---

## Pasos comunes (ambas opciones)

1. **Servidor con Docker:** Ubuntu 22.04+ con Docker Engine y el plugin
   `docker compose`.
2. **Clonar el repo:**
   ```bash
   git clone https://github.com/Jorgeperezr/clinica-odontologica.git
   cd clinica-odontologica
   ```
3. **Configurar el entorno:**
   ```bash
   cp .env.production.example .env
   nano .env   # completar TODOS los CAMBIAR- y el dominio real
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"  # para la SECRET_KEY
   ```
4. **Levantar:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
5. **Crear el superusuario:**
   ```bash
   docker compose -f docker-compose.prod.yml exec django-api python manage.py createsuperuser
   ```
6. **Verificar:** `curl -I http://localhost` debe devolver 200 (panel) y
   `http://localhost/api/v1/schema/swagger-ui/` debe cargar.

## Opción A — VM en GCP

1. Crear VM e2-medium (2 vCPU, 4 GB) en `southamerica-west1`, Ubuntu 22.04,
   disco 30 GB. Reservar IP estática.
2. Firewall: permitir 80 y 443.
3. Apuntar el dominio (registro A) a la IP.
4. TLS con certbot en el host + Nginx del host como proxy, o Cloudflare
   proxied DNS (más simple: activar el proxy naranja de Cloudflare y usar
   modo Full).
5. En `.env`: `SECURE_SSL_REDIRECT=True` si el TLS es propio (certbot).
6. Backups: activar snapshots diarios del disco en GCP.

## Opción B — PC en la clínica + Cloudflare Tunnel

1. PC dedicada (8+ GB RAM recomendado) con Ubuntu Server y Docker, UPS si
   es posible.
2. Dominio en Cloudflare (el DNS del dominio debe estar en Cloudflare).
3. Instalar el túnel:
   ```bash
   # En el host (fuera de Docker):
   curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
   sudo dpkg -i cloudflared.deb
   cloudflared tunnel login
   cloudflared tunnel create clinica
   cloudflared tunnel route dns clinica clinica.tudominio.ec
   ```
4. Configurar `/etc/cloudflared/config.yml`:
   ```yaml
   tunnel: clinica
   credentials-file: /root/.cloudflared/<ID>.json
   ingress:
     - hostname: clinica.tudominio.ec
       service: http://localhost:80
     - service: http_status:404
   ```
5. `sudo cloudflared service install && sudo systemctl start cloudflared`
6. En `.env`: `SECURE_SSL_REDIRECT=False` (Cloudflare ya fuerza HTTPS).

## Backups CIFRADOS (obligatorio en la Opción B, recomendado en la A)

Hay **dos copias distintas** y conviene no confundirlas, porque protegen
cosas diferentes y las hace gente diferente:

| | Copia de la plataforma | Copia de la clínica |
|---|---|---|
| Qué contiene | La base entera: **todas** las clínicas | Los datos de **una** clínica |
| Quién la hace | Quien administra el servidor | La administradora de la clínica |
| Desde dónde | `scripts/backup.sh` en el servidor | Panel → Configuración → Copia de seguridad |
| Clave | `BACKUP_PASSPHRASE` del `.env` | La frase que escribe en pantalla |
| Sirve para | Recuperar el servicio ante un desastre | Que la clínica conserve y consulte sus datos |
| Restaura | Sí, con `scripts/restore.sh` | No: solo descifra y muestra el contenido |

La copia de la clínica **no sustituye** a la de la plataforma: no incluye
los archivos adjuntos ni permite levantar el servicio de nuevo. La de la
plataforma sigue siendo obligatoria.

### Copia de la plataforma (servidor)

El repo incluye `scripts/backup.sh` (exporta toda la base — pacientes,
registros clínicos, pagos — y la cifra con AES-256) y `scripts/restore.sh`
(restaura un backup ante un error, con confirmación explícita).

Configuración (una vez):
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# → pegar el resultado en BACKUP_PASSPHRASE del .env
# → guardar una COPIA de esa clave fuera del servidor (gestor de
#   contraseñas / papel en caja fuerte): sin ella el backup no se
#   puede descifrar.
```

Copia manual: `COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh`

Los guiones funcionan **con Docker y sin él**: si no hay demonio usan el
`pg_dump` / `psql` de la máquina. Eso permite hacer y comprobar copias
desde un portátil sin Docker Desktop.

Cron diario:
```bash
# /etc/cron.d/backup-clinica  (02:00 todos los días)
0 2 * * * root cd /ruta/al/repo && COMPOSE_FILE=docker-compose.prod.yml ./scripts/backup.sh >> /var/log/backup-clinica.log 2>&1
```

### Verificación: una copia sin restaurar no es una copia

`backup.sh` comprueba al terminar que el volcado **está completo** —que
el SQL termina donde `pg_dump` lo cierra—. Eso descarta el fallo más
común y más silencioso: que la exportación se corte a la mitad porque se
llenó el disco o se reinició el contenedor.

Antes esa comprobación era `gzip -t`, que solo prueba que el archivo se
descomprime. **Un volcado partido por la mitad comprime perfectamente y
pasaba la prueba**: se anunciaba «correcto» una copia irrecuperable.
Verificado cortando un volcado a propósito.

Pero que el archivo esté entero no significa que se pueda restaurar. Eso
solo lo dice restaurarlo:

```bash
./scripts/verificar-backup.sh            # la copia más reciente
./scripts/verificar-backup.sh <archivo>  # una concreta
```

Descifra, **restaura de verdad en una base desechable**, cuenta las filas
de las tablas que importan y la destruye al salir. Nunca toca la base
real: el nombre de la base de prueba se genera con marca de tiempo y el
guion aborta si coincidiera con la de producción.

Devuelve `0` si la copia sirve y distinto de `0` si no, para poder
avisar. Comprobado que **falla** ante los cuatro casos que importan: un
volcado truncado, uno con esquema pero sin datos, la frase de cifrado
equivocada y un archivo inexistente.

Semanal:
```bash
# /etc/cron.d/verificar-backup-clinica  (domingos a las 03:00)
0 3 * * 0 root cd /ruta/al/repo && COMPOSE_FILE=docker-compose.prod.yml ./scripts/verificar-backup.sh >> /var/log/verificar-backup.log 2>&1 || mail -s "FALLO: la copia de la clinica NO es restaurable" tu@correo.ec
```

### En macOS

macOS trae **LibreSSL**, no OpenSSL, y su `enc` no siempre acepta
`-pbkdf2`. Sin esa opción el cifrado caería a una derivación de clave
mucho más débil y —lo grave— no podría descifrar las copias hechas en el
servidor. Los tres guiones lo comprueban antes de escribir nada y
explican qué hacer:

```bash
brew install openssl@3
export PATH="$(brew --prefix openssl@3)/bin:$PATH"
```

### Restauración ante un error real

```bash
COMPOSE_FILE=docker-compose.prod.yml ./scripts/restore.sh backups/clinica-2026-07-09_0200.sql.gz.enc
```

Comprueba que la copia esté completa **antes** de tocar la base: descubrir
que estaba truncada después de haberla borrado es la peor secuencia
posible, y era la que permitía el guion anterior.

Copiar `backups/` a un destino EXTERNO (rclone a Google Drive, disco USB
rotado). Un backup que vive en la misma máquina no es backup. Y probar la
restauración al menos una vez antes de tener pacientes reales.

### Copia de la clínica (panel)

En **Configuración → Copia de seguridad**, la administradora de la
clínica genera un archivo `.clinicabk` con los datos de su clínica y lo
vuelve a abrir desde la misma pantalla escribiendo su frase de cifrado.

- Cifrado AES-256-GCM con clave derivada por PBKDF2-HMAC-SHA256
  (400 000 iteraciones). El archivo va autenticado: si se altera un solo
  byte, no se abre.
- **La frase no se guarda en ninguna parte**, tampoco en la auditoría.
  Perderla equivale a perder el archivo.
- Solo el rol `admin` **de la clínica**. El Super Administrador de la
  plataforma no puede emitir ni abrir estas copias: administra el
  servicio, no es titular de los datos de ninguna clínica.
- Descifrar no restaura nada. Reponer datos sobre la base sigue siendo
  una operación de servidor (`scripts/restore.sh`), no de panel.
- El JSON descifrado que se descarga va **sin cifrar** y contiene datos
  de salud: hay que borrarlo del equipo al terminar (LOPDP).

## Actualizaciones del sistema

```bash
cd /ruta/al/repo
git pull
docker compose -f docker-compose.prod.yml up -d --build
```
(Las migraciones corren solas en el arranque.)

## Sondas de salud y orden de arranque

Django expone dos rutas **públicas y sin autenticación** (un monitor no
tiene credenciales):

| Ruta | Pregunta | Toca la base de datos |
|---|---|---|
| `GET /api/v1/health/` | ¿Está vivo el proceso? | No |
| `GET /api/v1/ready/` | ¿Puede atender? | Sí (`SELECT 1`) |

Son dos preguntas distintas y conviene no mezclarlas. Si `/ready/`
devuelve 503, el proceso está sano pero le falta la base: hay que sacarlo
del reparto de tráfico, **no reiniciarlo**. Reiniciar procesos sanos
porque la base tiene un mal momento convierte una incidencia en una
caída.

Ninguna de las dos revela versión, motor, nombre de clínica ni cuentas:
el detalle del error va al registro, porque el mensaje de la base lleva
host, puerto y usuario.

**Orden de arranque.** `docker-compose.prod.yml` no tenía sonda en
Postgres —el de desarrollo sí—, así que `depends_on: postgres` solo
esperaba a que el contenedor arrancara. En un arranque en frío o tras
reiniciar el host, `migrate` corría contra una base que aún no aceptaba
conexiones; el contenedor moría, `restart: unless-stopped` lo reintentaba
y acababa levantando, pero con un ciclo de caídas. Ahora:

- `postgres` y `redis` tienen sonda propia.
- `django-api` espera a que ambas estén sanas y publica la suya
  (`/api/v1/ready/`, consultada con `urllib`: la imagen `python:3.12-slim`
  no trae `curl` ni `wget`).
- `celery-worker`, `celery-beat` y `nginx` esperan a que Django **atienda**,
  no a que exista. Antes subían mientras aún corrían `migrate` y
  `collectstatic`, y las primeras peticiones devolvían 502.

Para monitorización externa (uptime, alertas), la ruta a vigilar es
`/api/v1/ready/`.

## Registro y diagnóstico

**El problema que había.** El proyecto no tenía bloque `LOGGING`, y eso no
significaba «el de Django por defecto»: significaba **silencio**.
Comprobado con un 500 real y `DEBUG=False` — el cliente recibe su 500 y la
traza no aparece en ningún sitio, ni en la salida estándar. El único
logger que trae Django es `django`, con el manejador `console` filtrado
por `require_debug_true` (callado en producción) y `mail_admins`, que
necesita `ADMINS` y un backend de correo; `ADMINS` estaba vacío. Cuando el
panel fallaba, nadie llegaba a enterarse de por qué.

**Cómo queda.** Una línea por petición a la salida estándar, que es donde
la recoge Docker:

```
DJANGO_LOG_FORMAT=json   # por defecto con DEBUG=False
DJANGO_LOG_FORMAT=plain  # por defecto en desarrollo
DJANGO_LOG_LEVEL=INFO
```

```json
{"ts":"...","level":"ERROR","logger":"apps.request","msg":"Excepción no controlada",
 "request_id":"34cb3d80bf9f4d4d","method":"GET","path":"/api/v1/patients/",
 "query_keys":["search"],"user_id":"...","tenant_id":"...",
 "exc_type":"RuntimeError","traceback":"..."}
```

**Correlación.** Cada petición lleva un `request_id` que va también en la
cabecera `X-Request-ID` de la respuesta. Si un usuario reporta un fallo y
da ese código, la incidencia se encuentra sin buscar por hora y a ojo.
Si nginx o el gateway mandan ya un `X-Request-ID`, se respeta, de modo que
una petición se sigue de punta a punta.

**Qué NO va al registro.** Esto es un sistema de datos de salud y un
registro se copia a un agregador, se conserva meses y lo lee gente que no
tiene por qué ver la historia de nadie:

| Sí | No |
|---|---|
| método, ruta, estado, duración | nombres, cédulas, teléfonos, correos |
| id de usuario, rol, id de clínica | contraseñas, tokens, cabeceras de auth |
| tipo de excepción y traza | contenido de notas clínicas |
| **nombres** de los parámetros de consulta | **valores** de esos parámetros |

Esa última fila importa más de lo que parece: `/api/v1/patients/?search=Pérez`
lleva un apellido dentro de la URL. Se registra `query_keys: ["search"]` y
nunca su contenido. Por el mismo motivo se descarta el logger
`django.request`, que pasa el objeto de petición en `extra` y cuyo repr
incluye la cadena de consulta entera.

Los UUID sí se registran: son seudónimos, sin la base de datos no dicen
quién es nadie, y sin ellos no se puede reconstruir qué pasó.

**Qué monitorizar.** Alertar sobre líneas con `level: ERROR` del logger
`apps.request`, y sobre `/api/v1/ready/` devolviendo 503. Las sondas de
salud no se registran a propósito: un balanceador las pide cada diez
segundos y ahogarían todo lo demás.

## Google Calendar — estado y Fase 2

**Fase 1 (ya funciona, sin credenciales):** cada doctor tiene un feed
iCalendar con URL secreta (Agenda → filtrar por doctor → "🗓 Calendario
del doctor"). Al suscribirla en Google Calendar (Otros calendarios → + →
Desde URL), las citas de la clínica aparecen en su calendario personal y
se actualizan solas (Google refresca las suscripciones cada varias horas).

**Fase 2 (bidireccional real — pendiente de credenciales):** que un evento
creado en el Google Calendar del doctor bloquee su agenda en la clínica.
Requiere: proyecto en Google Cloud Console → habilitar Google Calendar API
→ credenciales OAuth 2.0 (client ID + secret) → pantalla de consentimiento.
El campo `Appointment.google_calendar_event_id` ya existe en el modelo
para ese momento. Cuando tengas las credenciales, se implementa el flujo
OAuth por doctor y la sincronización con webhooks push de Google.

## firmaEC — firma electrónica legal (Fase 2)

Las recetas se generan en PDF profesional con la firma manuscrita del
doctor estampada (dibujada en "Mi firma"). Para la firma electrónica
LEGAL de Ecuador (firmaEC): cada doctor necesita su certificado digital
`.p12` emitido por una entidad acreditada (Registro Civil, Security Data,
UANATACA, ANF). Con esos certificados se integra el firmado PAdES del
PDF (librería endesive) — mismo patrón que Meta y Google: el código
queda listo, faltan las credenciales del trámite.

## Archivos subidos (`/media/`)

Nginx sirve desde disco **únicamente** `/media/branding/` — el logotipo de la
clínica, que es público y va en un `<img>` sin sesión. Cualquier otra ruta
bajo `/media/` devuelve 404 a propósito.

El resto de lo que hay ahí dentro son radiografías, documentos de pacientes,
consentimientos firmados y firmas manuscritas. Nginx no sabe quién pide un
archivo, así que publicarlos por esa vía los dejaría al alcance de cualquiera
que acertara la URL, sin sesión y sin registro de acceso. Se entregan por la
API (`/api/v1/patients/{id}/documents/{doc}/file/`), que valida clínica,
paciente y permisos antes de devolver el binario.

**Si alguna vez hace falta publicar una carpeta nueva**, añádele su propio
`location` con `alias`; no amplíes el de `branding` ni sustituyas el `return
404` por un `alias` general.

Con `USE_CLOUD_STORAGE=True` los archivos van al bucket y esto no aplica:
las URLs son absolutas y el control de acceso lo da el propio bucket, que debe
quedar **privado** por el mismo motivo.

## Pendientes ANTES de pacientes reales

- [ ] Cambiar TODAS las contraseñas de desarrollo (Jorge2025 no va a producción).
- [ ] Plantilla `recordatorio_cita` en Meta con 3 variables (nombre, fecha,
      instrucción de confirmación) — el webhook ya entiende "CONFIRMO"/"sí".
- [ ] Credenciales de Meta en `.env` cuando la verificación esté aprobada
      (sin esto, los recordatorios WhatsApp quedan en modo simulado).
- [ ] Validar catálogo del odontograma y formularios por especialidad con el doctor.
- [ ] Revisión LOPDP con un abogado (aviso de privacidad, consentimiento de datos).
- [ ] Probar la restauración de un backup (un backup no probado no existe).
