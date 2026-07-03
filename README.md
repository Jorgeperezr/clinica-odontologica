# Sistema de Gestión — Clínica Odontológica

Monorepo con dos servicios de backend independientes:

- **`django-api/`** — Backend principal (Django + Django REST Framework). Fuente de verdad de todo el dominio: usuarios, pacientes, agenda, historia clínica, tratamientos, pagos, inventario, reportes y configuración.
- **`whatsapp-gateway/`** — Microservicio (FastAPI) dedicado a la integración con WhatsApp Business Cloud API de Meta: envío de plantillas, verificación y procesamiento del webhook.

Ver la documentación completa de las 7 fases previas (PRD, SRS, Arquitectura, Modelo de datos, APIs, Backlog, Roadmap) en los documentos ya entregados.

## Estado actual: Sprint 1 completado

### Sprint 0 — Fundamentos técnicos (hecho)

Lo que ya existe en este scaffold:
- Estructura de apps de Django según el Modelo de datos (`accounts`, `patients`, `agenda`, `clinical`, `specialties`, `billing`, `inventory`, `whatsapp`, `configuration`).
- Modelo `Tenant` + middleware multi-tenant (app `common`).
- Modelo `User` personalizado (JWT para staff, OTP para pacientes), `AuditLog`, `OTPCode`, `DeviceToken` (app `accounts`).
- Autenticación JWT (`djangorestframework-simplejwt`) y endpoints base de login/refresh.
- Registro de auditoría automático vía middleware para requests autenticados que modifican datos.
- `docker-compose.yml` con Nginx + Django + FastAPI + PostgreSQL + Redis + Celery worker/beat.
- Esqueleto de `whatsapp-gateway` (FastAPI) con health check, endpoint interno `/internal/send-template` (stub) y webhook `/whatsapp/webhook` (verificación + recepción, con validación de firma).
- Pipeline de CI básico (GitHub Actions): lint + tests en cada push.

### Sprint 1 — Usuarios completo + arranque de Pacientes (hecho)
- **Usuarios:** login staff (JWT), OTP por WhatsApp para pacientes, recuperación de acceso (staff por correo, paciente por reenvío de OTP), gestión de usuarios (alta/edición/baja lógica, solo admin), listado de auditoría filtrable.
- **Pacientes:** registro con validación de cédula única por sede, búsqueda por nombre/cédula/teléfono, antecedentes médicos (con auditoría explícita de acceso, exigida por LOPDP), documentos adjuntos, y endpoint base de línea de tiempo del historial.
- **Tests:** 10 tests automatizados (autenticación, permisos por rol, unicidad de cédula, control de acceso clínico) — todos en verde.
- **Bugs corregidos en el proceso:** carpeta `migrations/` faltante en `common`; `TenantMiddleware` que resolvía el tenant antes de la autenticación JWT (corregido con resolución perezosa); tasa de throttle de OTP en formato inválido para DRF.

Correr los tests:
```bash
docker compose exec django-api python manage.py test --settings=config.settings_test
# o en local sin docker:
cd django-api && python manage.py test --settings=config.settings_test
```

Lo que **no** está implementado todavía (siguientes sprints del Roadmap): lógica de negocio de pacientes, agenda, historia clínica/odontograma, tratamientos/pagos, inventario, reportes, ni la app Flutter ni el panel Next.js.

## Cómo levantar el entorno local

```bash
cp .env.example .env
# editar .env con valores locales (nunca commitear el .env real)

docker compose up --build
```

Esto levanta:
- `nginx` → http://localhost (proxy a Django y al webhook de FastAPI)
- `django-api` → Django + Gunicorn detrás de Nginx
- `whatsapp-gateway` → FastAPI + Uvicorn detrás de Nginx
- `postgres`, `redis`
- `celery-worker`, `celery-beat`

Para desarrollo puro de API sin Nginx:
```bash
docker compose up postgres redis django-api whatsapp-gateway
# Django: http://localhost:8000
# FastAPI: http://localhost:8001
```

### Primer arranque (superusuario)

Las migraciones y la creación de un tenant por defecto corren
automáticamente al levantar `docker compose up`. Solo falta crear tu
superusuario:

```bash
docker compose exec django-api python manage.py createsuperuser
```

El superusuario se asigna automáticamente al tenant por defecto que creó
el arranque. Luego entrá a http://localhost/admin/

> Nota sobre el arranque en frío: el modelo de usuario exige un tenant.
> El comando `bootstrap` (que corre solo en `docker compose up`) crea un
> tenant por defecto para resolver esto. Si corrés el proyecto sin Docker,
> ejecutá `python manage.py bootstrap` antes de `createsuperuser`.

## Desarrollo en GitHub Codespaces

Este repo funciona bien en Codespaces para `django-api/`, `whatsapp-gateway/` y (más adelante) el panel Next.js — todo corre sobre Docker dentro del devcontainer. El desarrollo de la app Flutter requiere emulador con aceleración gráfica, por lo que se recomienda hacerlo en una máquina local (o dispositivo físico) en paralelo, no dentro de Codespaces.

## Hosting de producción

Pendiente de definir (VM en GCP vs. PC física con túnel) — no afecta el desarrollo, que es idéntico en ambos casos vía Docker Compose. Se resuelve antes de la Fase 12 (Despliegue).
