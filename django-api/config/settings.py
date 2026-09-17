"""
Django settings — Clínica Odontológica.

Fase 8 / Sprint 0: fundamentos técnicos.
Todo valor sensible viene de variables de entorno (.env en local;
Secret Manager en producción, según la Arquitectura v1.2). Nunca se
hardcodean secretos en este archivo.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# Orígenes confiables para CSRF. Necesario cuando el sitio se sirve
# detrás de un proxy TLS externo (Codespaces, Cloudflare Tunnel, etc.)
# porque Django requiere que el 'Origin' del POST coincida con uno de estos.
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost,http://127.0.0.1",
    cast=Csv(),
)

# ── Seguridad de producción (Fase 12) ────────────────────────────────
# Activa cabeceras y cookies seguras cuando DEBUG=False. El TLS lo
# termina el proxy (Nginx con certificado, o Cloudflare Tunnel), por lo
# que Django confía en X-Forwarded-Proto para saber si el request
# original fue HTTPS.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

    # SSL redirect: apagado por defecto porque detrás de Cloudflare
    # Tunnel el redirect puede generar bucles; encender solo con Nginx+TLS
    # propio via env.
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)

    # HSTS: empezar corto (1 hora) y subir a 31536000 cuando el dominio
    # esté estable en HTTPS.
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=3600, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True


# --------------------------------------------------------------------------
# Apps
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    # Apps del dominio (una por módulo del SRS / Modelo de datos)
    "apps.common",
    "apps.accounts",
    "apps.patients",
    "apps.agenda",
    "apps.clinical",
    "apps.specialties",
    "apps.billing",
    "apps.inventory",
    "apps.whatsapp",
    "apps.app_paciente",
    "apps.configuration",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    # El primero de la lista a propósito: su process_request abre el
    # cronómetro antes que nadie y su process_response —que se ejecuta en
    # orden inverso— es el último en ver la respuesta, así que mide la
    # petición entera y no un trozo.
    "apps.common.middleware.RequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Middlewares propios (Sprint 0 — HU-INF-02, HU-INF-05)
    "apps.common.middleware.TenantMiddleware",
    "apps.accounts.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Base de datos (PostgreSQL — ver Arquitectura v1.2)
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="clinica"),
        "USER": config("POSTGRES_USER", default="clinica"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="clinica"),
        "HOST": config("POSTGRES_HOST", default="postgres"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Password validation
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internacionalización
# --------------------------------------------------------------------------
LANGUAGE_CODE = "es-ec"
# Configurable por entorno: el sistema es multiclínica y una sede en otro
# huso necesita el suyo. En pruebas sirve además para reproducir el
# desfase entre la fecha del servidor y la fecha local de la clínica,
# que es de donde han salido varios fallos de frontera de fecha.
TIME_ZONE = config("DJANGO_TIME_ZONE", default="America/Guayaquil")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.common.authentication.TenantAwareJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # 60/min era demasiado poco, y no por teoría: recorriendo el panel
        # con un navegador de verdad, abrir UNA ficha clínica y mirar sus
        # pestañas gasta unas treinta peticiones. En una sesión ya
        # empezada bastaron 22 más para recibir un 429, y entonces la
        # pestaña de planes se quedaba EN BLANCO —la pantalla entera pasó
        # de 2053 caracteres a cero—. Es decir: el límite pensado para
        # frenar un abuso estaba frenando a la recepcionista al segundo
        # paciente de la mañana.
        #
        # 600/min son diez peticiones por segundo sostenidas: ninguna
        # persona se acerca, y un bucle desbocado o un token robado
        # siguen teniendo techo. Quien de verdad protege el login es el
        # límite de anónimo, que no se toca.
        #
        # Si algún día el panel deja de pedir treinta cosas por ficha,
        # este número puede bajar. Mientras las pida, bajarlo es romper
        # la aplicación a propósito.
        "user": "600/min",
        "anon": "20/min",
        "otp": "5/min",  # aprox. válida; ventana exacta de 10 min se afina en Sprint 10
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API — Clínica Odontológica",
    "DESCRIPTION": "Ver el documento 05-APIs-Clinica-Odontologica.md para el contrato completo.",
    "VERSION": "1.0.0",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:3000", cast=Csv())

# En producción el panel y la API comparten origen tras nginx, pero en
# desarrollo el panel corre en otro puerto y el navegador oculta las
# cabeceras de respuesta que no se declaren aquí. Sin esto, una descarga
# generada por la API llega sin su nombre de archivo.
CORS_EXPOSE_HEADERS = ["Content-Disposition"]

# --------------------------------------------------------------------------
# Celery / Redis (recordatorios, tareas programadas — ver Arquitectura v1.2)
# --------------------------------------------------------------------------
CELERY_BROKER_URL = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# --------------------------------------------------------------------------
# Integración con el microservicio de WhatsApp (FastAPI)
# --------------------------------------------------------------------------
WHATSAPP_GATEWAY_URL = config("WHATSAPP_GATEWAY_URL", default="http://whatsapp-gateway:8001")
INTERNAL_SERVICE_TOKEN = config("INTERNAL_SERVICE_TOKEN", default="dev-only-shared-secret-change-me")

# --------------------------------------------------------------------------
# Almacenamiento de archivos (Cloud Storage en producción — ver Arquitectura)
# --------------------------------------------------------------------------
USE_CLOUD_STORAGE = config("USE_CLOUD_STORAGE", default=False, cast=bool)

# MEDIA_URL y MEDIA_ROOT se definen SIEMPRE: los FieldFile construyen su
# ruta con ellos incluso cuando el backend es un bucket, y dejarlos solo
# en la rama local hacía que con Cloud Storage salieran rutas vacías.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if USE_CLOUD_STORAGE:
    # Django 5 configura el almacenamiento por STORAGES. Aquí se usaba
    # además DEFAULT_FILE_STORAGE, y las dos formas son EXCLUYENTES: con
    # USE_CLOUD_STORAGE=True el proyecto ni siquiera arrancaba
    # (ImproperlyConfigured). Nadie lo había notado porque el interruptor
    # todavía no se ha encendido en ningún despliegue.
    STORAGES["default"] = {"BACKEND": "storages.backends.gcloud.GoogleCloudStorage"}
    GS_BUCKET_NAME = config("GS_BUCKET_NAME", default="")


# --------------------------------------------------------------------------
# Registro (Sprint 75)
# --------------------------------------------------------------------------
# No había bloque LOGGING, y eso NO significaba «el de Django por defecto»:
# significaba silencio. Comprobado con un 500 real y DEBUG=False —el cliente
# recibe su 500 y la traza no aparece en ningún sitio, ni en la salida
# estándar—, porque el único logger que trae Django es `django`, con los
# manejadores `console` (filtrado por require_debug_true, callado en
# producción) y `mail_admins` (necesita ADMINS, que está vacío).
#
# Formato: JSON en producción, porque el destino es un agregador y allí
# poder filtrar por estado o por id de petición vale más que leerse bonito;
# texto plano en desarrollo. Se elige con DJANGO_LOG_FORMAT.
#
# Qué NO va al registro —nombres, cédulas, teléfonos, contraseñas— y por
# qué: ver la cabecera de apps/common/logging.py. Es un sistema de datos de
# salud y un registro se copia, se conserva y lo lee gente que no tiene por
# qué ver la historia de nadie.

LOG_LEVEL = config("DJANGO_LOG_LEVEL", default="INFO").upper()
LOG_FORMAT = config("DJANGO_LOG_FORMAT", default="plain" if DEBUG else "json")

LOGGING = {
    "version": 1,
    # Los loggers que el proyecto ya tenía (apps.common.health,
    # apps.whatsapp...) siguen funcionando: no se desactiva nada.
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.common.logging.RequestIdFilter"},
    },
    "formatters": {
        "json": {"()": "apps.common.logging.JsonFormatter"},
        "plain": {"()": "apps.common.logging.PlainFormatter"},
    },
    "handlers": {
        # Descarta de verdad. Con `"handlers": []` no basta: Python cae
        # entonces en `logging.lastResort`, que escribe en stderr sin
        # formato — comprobado, salía la traza duplicada y en texto plano.
        "null": {"class": "logging.NullHandler"},
        # A la salida estándar, SIN filtro de DEBUG: es justo el filtro que
        # dejaba mudo el registro en producción. En contenedores, stdout es
        # el sitio correcto: lo recoge Docker y de ahí el agregador.
        "console": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # django.request registra el 500 por su cuenta, ADEMÁS del nuestro:
        # dos trazas completas por cada fallo, y la suya llega con el
        # objeto `request` en extra, cuyo repr lleva la cadena de consulta
        # entera —o sea, apellidos de pacientes—. Se deja sin manejadores
        # y sin propagar: la fuente única es RequestLogMiddleware, que
        # registra lo mismo con contexto y sin datos personales.
        # (La clave `request` se tapa igualmente en el formateador, por si
        # otro logger vuelve a pasar un objeto de petición.)
        "django.request": {"handlers": ["null"], "propagate": False},
        # Una línea por consulta SQL ahoga cualquier otra cosa. Se sube a
        # WARNING; quien quiera verlas pone DJANGO_LOG_LEVEL=DEBUG y cambia
        # esto a mano, que es una decisión consciente y no un descuido.
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        # El registro de acceso de runserver duplica lo que ya escribe el
        # middleware —con menos contexto y sin id de correlación—, y en
        # producción esa capa la sirve gunicorn. A la basura, igual que
        # django.request y por el mismo motivo: una línea por petición, no
        # tres.
        "django.server": {"handlers": ["null"], "propagate": False},
    },
}
