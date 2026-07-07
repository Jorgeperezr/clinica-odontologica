"""
Settings para ejecución de tests.

Usa SQLite en memoria para que la suite corra rápido y sin depender de
un PostgreSQL levantado (útil en CI y en desarrollo local rápido). El
comportamiento de la app en producción sigue siendo PostgreSQL (config.settings).

Uso:
    python manage.py test --settings=config.settings_test
"""

from config.settings import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Acelera los tests (hashing de contraseñas trivial en entorno de test).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Celery en modo síncrono para tests: las tareas .delay() se ejecutan
# inmediatamente en el mismo proceso, sin necesidad de Redis/broker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
