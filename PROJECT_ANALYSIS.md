# PROJECT_ANALYSIS — Sistema de Gestión para Clínica Odontológica

> Análisis de arquitectura y estado del proyecto, realizado sobre el código real
> del repositorio (rama `main`, tras el Sprint 52). Verificado ejecutando la
> suite de tests del backend (161 tests), el linter (`ruff`) y el build estático
> del panel Next.js — resultados en la sección [Estado verificado](#5-estado-verificado-del-proyecto).

---

## 1. Resumen ejecutivo

Sistema SaaS multi-tenant para la gestión integral de clínicas odontológicas en
Ecuador, alineado con el formulario oficial MSP HCU-033/2021 y con la LOPDP
(auditoría de acceso a datos clínicos, borrado lógico, opt-in de mensajería).

El proyecto está en un estado **muy avanzado y funcional**: backend completo
(10 módulos de dominio), panel web completo (7 secciones + panel de plataforma
para el superadministrador), microservicio de WhatsApp operativo en modo
simulado, CI en verde y documentación de despliegue. Lo pendiente de mayor
tamaño es la **app móvil de pacientes (Flutter)**, la **activación real de
WhatsApp** (credenciales de Meta) y la **decisión/ejecución del hosting de
producción**.

| Dimensión | Estado |
|---|---|
| Backend (Django + DRF) | Completo — 10 apps, 161 tests |
| Panel web (Next.js 14) | Completo — 12 páginas, build estático OK |
| Gateway WhatsApp (FastAPI) | Completo en modo simulado; sin credenciales Meta |
| App móvil (Flutter) | No iniciada |
| Despliegue a producción | Preparado (compose prod, DEPLOY.md); hosting sin decidir |
| CI (GitHub Actions) | Lint + tests backend, lint gateway, build frontend |

---

## 2. Arquitectura

### 2.1 Vista de servicios (docker-compose)

```
                        ┌──────────────┐
   navegador ──http──▶  │    nginx     │  puerto 80
                        └──────┬───────┘
        ┌──────────────────────┼───────────────────────────┐
        │ /api/ /admin/        │ /whatsapp/webhook         │ /  (panel estático
        │ /media/ /static/     │                           │    en producción)
        ▼                      ▼                           ▼
 ┌─────────────┐      ┌──────────────────┐        Next.js (dev: puerto 3000;
 │ django-api  │◀────▶│ whatsapp-gateway │        prod: export estático servido
 │ (gunicorn)  │ token│    (FastAPI)     │        por nginx desde volumen)
 └──┬───┬──────┘ int. └────────┬─────────┘
    │   │                      │  Meta WhatsApp Cloud API (simulado sin credenciales)
    ▼   ▼
 postgres  redis ◀── celery-worker / celery-beat
```

- **`django-api/`** — Fuente de verdad de todo el dominio. Django 5.0 + DRF 3.15,
  PostgreSQL 16, JWT (simplejwt con rotación y blacklist), Celery 5.4 + Redis
  para tareas (recordatorios, morosidad diaria), drf-spectacular (OpenAPI en
  `/api/v1/schema/swagger-ui/`).
- **`whatsapp-gateway/`** — Microservicio FastAPI sin lógica de negocio: envía
  plantillas a Meta y traduce el webhook (estados de entrega, mensajes
  entrantes) a eventos internos que reenvía a Django. Comunicación protegida
  con `INTERNAL_SERVICE_TOKEN` compartido; firma del webhook de Meta verificada.
- **`frontend/`** — Next.js 14 (App Router, JavaScript, `"use client"`), sin
  framework de UI: sistema de diseño propio con tokens CSS (temas claro/oscuro,
  personalización de marca por clínica). En producción se exporta a estático
  (`output: "export"`) y lo sirve nginx.
- **`nginx/`** — Proxy único de entrada: API/admin/media → Django, webhook →
  gateway, resto → panel estático.

### 2.2 Multi-tenancy

- `common.Tenant` (clínica) + abstracta `TenantAwareModel` (UUID pk, FK a
  tenant, timestamps) heredada por todos los modelos de dominio.
- `TenantMiddleware` resuelve el tenant del usuario autenticado (resolución
  perezosa, post-JWT) y las vistas filtran siempre por `request.tenant`.
- `TenantAwareJWTAuthentication`: al suspender una clínica sus usuarios pierden
  acceso al instante aunque tengan tokens vigentes.
- Jerarquía de roles: `superadmin` (plataforma, sin tenant) → por clínica:
  `admin`, `doctor`, `reception`, `auxiliary`. El superadmin **no** accede a
  datos operativos (verificado por tests).
- Aislamiento entre clínicas cubierto por tests (listado y lectura por ID).

### 2.3 Patrones de diseño empleados

- **Servicios de dominio**: `billing/services.py` centraliza la definición de
  "paciente moroso" (usada por agenda, reportes y la tarea Celery);
  `inventory/services.py` el descuento FEFO de stock.
- **Strategy en el odontograma** (`frontend/lib/odontogram/`): `contract.js`
  define el contrato, `registry.js` es el punto único de extensión; 4 vistas
  intercambiables (Clásico MSP, Anatómico, Ficha periodontal, 3D) sobre una
  única fuente de datos. Solo la ficha periodontal es un híbrido documentado
  (tiene endpoints propios para mediciones periodontales).
- **Registro histórico inmutable** en el odontograma (`ToothRecord`): nunca se
  sobrescribe; el "estado actual" se deriva del último registro por
  pieza/superficie.
- **Soft delete** (`SoftDeleteModel`) para datos clínicos y financieros; nunca
  DELETE físico.
- **Auditoría transversal**: `AuditLogMiddleware` para escrituras + auditoría
  explícita de lecturas clínicas (exigencia LOPDP), `ConsentAuditLog` por
  consentimiento.
- **Configuración parametrizable sin código**: `SystemParameter` (clave-valor:
  morosidad, recordatorios, alertas), catálogo de estados del odontograma,
  plantillas de planes y de consentimientos.

---

## 3. Modelo de datos (50 modelos, 10 apps)

| App | Modelos principales | Rol |
|---|---|---|
| `common` | Tenant, PlatformConfiguration | Multi-tenancy y configuración global del SaaS |
| `accounts` | User (email, roles), OTPCode, AuditLog, PasswordResetToken, DeviceToken | Identidad: JWT staff, OTP pacientes, auditoría |
| `patients` | Patient (+soft delete), MedicalBackground, PatientDocument | Padrón, antecedentes, documentos por categoría |
| `agenda` | Doctor (color, firma, licencia, feed iCal), Appointment (estados + check-in/atención/check-out) | Agenda con anti-solapamiento y bloqueo por morosidad |
| `clinical` | ClinicalRecord, Evolution, Diagnosis (CIE-10 PRE/DEF), TreatmentPlan(+Template), OdontogramState (catálogo 22 estados MSP), ToothRecord (pieza/superficie/movilidad/recesión), RadiographPhoto, InformedConsent (+ConsentTemplate, ConsentAuditLog, flujo de estados), Cie10, Form033Record, ExamRequest, PeriodontalExam/PeriodontalTooth (6 sitios) | Historia clínica completa alineada al Form. 033 |
| `specialties` | Specialty, SpecialtyForm (JSONField) | Formularios flexibles por especialidad |
| `billing` | Budget/BudgetItem, PaymentPlan/Installment (reparto exacto de centavos), Payment, DoctorFee | Presupuestos → cuotas → cobros; morosidad |
| `inventory` | Product, Batch (vencimiento), InventoryMovement | Stock con FEFO, alertas de mínimo y caducidad |
| `whatsapp` | WhatsAppTemplate, WhatsAppMessageLog, WhatsAppOptIn | Plantillas, trazabilidad de envíos, opt-in LOPDP |
| `configuration` | Treatment, Agreement, Tariff, SystemParameter, TreatmentInventoryItem, ClinicBranding | Catálogos, tarifarios, parámetros, identidad visual |

Convenciones: PK UUID en todo el dominio, `tenant` obligatorio, `created_at`/
`updated_at`, borrado lógico donde aplica. El nivel de inserción periodontal es
derivado (sondaje + margen), no almacenado — buen ejemplo del criterio general
de no duplicar datos derivables.

---

## 4. Módulos y estado de implementación

### 4.1 Terminado y probado (backend + panel)

- **Usuarios y seguridad**: login JWT, refresh con rotación/blacklist, OTP por
  WhatsApp para pacientes, recuperación de acceso, gestión de usuarios, throttling.
- **Pacientes**: registro (cédula única por sede), búsqueda, ordenamientos,
  vista lista/tarjetas, ficha completa con pestañas, cumpleaños, documentos
  (subida, escaneo por cámara a PDF, vista previa, borrado suave con permisos,
  descarga autenticada con validación de tenant).
- **Agenda**: día/semana/mes, anti-solapamiento, estados completos, flujo
  llegada → atención → salida, bloqueo por morosidad con override, aviso de
  pacientes en sala, color por profesional, feed iCalendar por doctor.
- **Historia clínica**: evoluciones con seguimientos, diagnósticos CIE-10
  (catálogo sembrado), planes con plantillas y progreso, consentimientos con
  firma táctil y flujo de estados (firmado = inmutable), recetas con firma
  manuscrita del doctor, solicitudes de examen con PDF, formulario MSP 033
  completo (literales A–O) con export a PDF y a la plantilla Excel oficial.
- **Odontograma**: 22 estados MSP por pieza/superficie, registro por
  simbología, histórico inmutable, índices CPO-ceo automáticos, 4 vistas
  (Strategy), ficha periodontal con 6 sitios e índices agregados.
- **Tratamientos y pagos**: presupuestos, aprobación, planes de cuotas con
  reparto exacto, cobros parciales, estado de cuenta, morosidad, honorarios,
  cobros directos desde la ficha.
- **Inventario**: productos, lotes, movimientos, alertas, descuento FEFO
  automático al completar tratamientos.
- **Reportes** (admin): financiero, morosidad, producción por doctor, pacientes
  nuevos, inventario, actividad de citas; exports a Excel; impresión.
- **Plataforma (superadmin)**: dashboard, gestión de clínicas y de sus
  administradores, auditoría propia, configuración global.
- **Personalización por clínica**: logo con recorte, extracción de paleta,
  6 temas + colores manuales con contraste WCAG AA garantizado, claro/oscuro.
- **WhatsApp (modo simulado)**: recordatorios de cita (idempotentes vía
  `reminder_sent_at`), recordatorios de pago, aviso de llegada, OTP,
  confirmación de cita por respuesta del paciente, opt-in.

### 4.2 Parcial / preparado pero no activo

| Funcionalidad | Estado | Qué falta |
|---|---|---|
| WhatsApp real | Gateway completo, modo simulado | Verificación del negocio en Meta + credenciales en `.env` (sin cambios de código) |
| Google Calendar | Fase 1 (feed iCal de solo lectura) operativa; `google_calendar_event_id` ya existe | Fase 2: OAuth2 bidireccional |
| Firma electrónica legal (firmaEC) | Firma manuscrita estampada operativa | Integración con certificados .p12 por doctor |
| Cloud Storage | `USE_CLOUD_STORAGE` + django-storages listos | Bucket GCS y activación (hoy: FileSystemStorage) |
| Hosting de producción | `docker-compose.prod.yml`, DEPLOY.md, scripts de backup cifrado | Decidir VM vs. PC+túnel y ejecutar la Fase 12 |
| Escáner de documentos | Captura por cámara con realce | Recorte de bordes/perspectiva (OpenCV.js) — documentado como mejora futura |

### 4.3 No iniciado

- **App móvil de pacientes (Flutter)** — el backend ya la contempla (OTP,
  `visible_to_patient` en evoluciones, DeviceToken).
- **Tests automatizados del frontend** y del **gateway** (CI solo lint/build).
- **Convenios/tarifarios en el panel** — modelos y API existen
  (`Agreement`, `Tariff`); no se encontró UI en Configuración.

---

## 5. Estado verificado del proyecto

Ejecutado durante este análisis (2026-07-31):

| Verificación | Resultado |
|---|---|
| `manage.py test --settings=config.settings_test` | **161 tests: 160 OK, 1 fallo** (ver abajo) |
| `ruff check apps config` | Sin errores |
| `next build` (export estático) | Compila sin errores |

**El único fallo es un test dependiente de la hora local**, no un bug de
producto: `apps.billing.tests.Sprint45Tests.test_waiting_patients_after_checkin`
crea una cita a `now + 1h`; ejecutado cerca de la medianoche de Guayaquil
(UTC-5) la cita cae en la fecha local siguiente y el endpoint
`appointments/waiting/` filtra por `scheduled_start__date=hoy`
(`agenda/views.py:366`). El mismo patrón de riesgo existe en el test de
cumpleaños. Es un test *flaky* de frontera de medianoche que puede pintar el CI
de rojo intermitentemente.

Nota de entorno: dos errores adicionales que aparecieron al primer intento
(`TokenBackend`/`cryptography`) eran del contenedor de análisis (paquete
`cryptography` del sistema roto), no del proyecto; con dependencias limpias no
ocurren.

---

## 6. Riesgos y deuda técnica

### 6.1 Riesgos técnicos

1. **Servido de `/media/` en producción (verificar antes del despliegue).**
   `nginx.conf` proxya `/media/` a Django, pero Django solo sirve media con
   `DEBUG=True` (`config/urls.py:32`). En `docker-compose.prod.yml` nginx monta
   `media_data` en `/app/media:ro` pero **no existe un `location` que sirva
   desde esa ruta**. Consecuencia probable: logos de clínica (que usan URL
   `/media/...` directa) devolverían 404 en producción. Los documentos de
   pacientes no se ven afectados (usan el endpoint autenticado del Sprint 38).
2. **Test flaky de medianoche** (sección 5): CI rojo intermitente ≈ 1 hora/día.
3. **JWT en `localStorage`** (`frontend/lib/api.js`): expuesto ante XSS. Riesgo
   moderado (no hay contenido de terceros inyectable hoy), pero una migración a
   cookies `httpOnly` o mitigaciones CSP es deseable antes de crecer.
4. **Sin tests del gateway FastAPI**: el parseo del webhook de Meta (crítico
   para confirmaciones de cita) solo tiene lint en CI.
5. **Sin observabilidad**: no hay Sentry/alertas ni logging estructurado;
   en producción los errores solo quedan en stdout de los contenedores.
6. **Backups**: scripts cifrados existen (`scripts/backup.sh`), pero no hay
   evidencia de programación automática (cron) ni de prueba de restauración
   periódica — crítico con datos de salud.

### 6.2 Deuda técnica y limpieza

1. **Código muerto de los Sprints 50–51**: `frontend/lib/odontogram/CompactView.js`,
   `AdvancedCompactView.js` y `advanced/AdvancedCompactView.js` ya no están
   referenciados (el registro usa `periodontal/PeriodontalMatrix`). Además,
   `PeriodontalMatrix.js` exporta una función llamada `AdvancedCompactView`
   (nombre heredado que confunde).
2. **README desactualizado en tres puntos**: dice "132 tests" (son 161); la
   línea final de la sección de estado conserva un texto residual del Sprint 0
   ("Lo que no está implementado todavía: … pacientes, agenda, …") que
   contradice todo lo anterior; y faltan las secciones de los Sprints 50–51
   (existen en el historial de git, el 52 los sustituyó). El README (72 KB) ya
   mezcla guía de uso con changelog — conviene separar un `CHANGELOG.md`.
3. **Páginas monolíticas en el frontend**: `configuracion/page.js` (866 líneas),
   `paciente/page.js` (630), `ClinicalTabs.js` (567), `plataforma/page.js`
   (532). Funcionan, pero elevan el costo de cada cambio.
4. **Frontend sin linter ni tipos**: no hay ESLint configurado ni TypeScript;
   el CI solo compila. Los bugs de los Sprints 41–42 (tupla vs. objeto de
   `useConfirm`) son exactamente la clase de error que estas herramientas
   atrapan.
5. **Throttle de OTP aproximado**: la ventana exacta de 10 minutos quedó
   anotada como pendiente en `settings.py:187`.
6. **Duplicidad latente `full_name` vs. `first_name/last_name`** entre `User`
   (full_name) y `Patient` (first/last) — no es un bug, pero obliga a
   formatear en cada vista.
7. **UI faltante para convenios y tarifarios** (backend listo desde Sprint 2).

### 6.3 Fortalezas a preservar

Multi-tenancy y auditoría desde el día 1; regla de negocio en el backend (la UI
solo refleja); tests de aislamiento entre clínicas; catálogos parametrizables
sin código; documentación de decisiones en el propio código; suite E2E que
recorre todos los módulos; accesibilidad (WCAG AA verificado, reduced-motion).

---

## 7. Oportunidades de mejora

- **Producto**: portal/app del paciente (el diferencial pendiente más grande);
  recordatorios por correo como plan B sin depender de Meta; agenda con lista
  de espera; caja diaria/cierre de caja; facturación electrónica SRI (Ecuador)
  como módulo futuro de alto valor.
- **Ingeniería**: contrato OpenAPI ya generado → cliente tipado para el
  frontend; snapshot de datos derivados costosos si el volumen crece (CPO-ceo
  e índices periodontales se calculan al vuelo — correcto hoy, medible mañana);
  índices de BD para búsquedas de pacientes cuando haya volumen real.
- **Operación**: entorno de staging con datos sintéticos; job de restauración
  de backup automatizado que valide el `.enc` semanalmente.

---

## 8. Roadmap propuesto (priorizado)

### P0 — Estabilización (esfuerzo bajo, riesgo que ya existe)
1. Corregir el test flaky de medianoche (congelar el tiempo en los tests de
   `waiting`/`birthdays` o crear las citas con fecha local controlada).
2. Verificar y corregir el servido de `/media/` en producción (añadir en nginx
   un `location /media/` con `root` al volumen, o servirlo vía endpoint).
3. Eliminar el código muerto de los Sprints 50–51 y renombrar el export de
   `PeriodontalMatrix`.
4. Actualizar el README: contador de tests (161), texto residual del estado,
   secciones 50–51; opcionalmente extraer el changelog.

### P1 — Camino a producción real (el mayor valor pendiente)
5. Decidir hosting (DEPLOY.md ya compara opciones) y ejecutar la Fase 12:
   dominio + TLS, `.env` de producción, HSTS definitivo.
6. Programar y **probar** backups automáticos (cron + restauración de prueba).
7. Completar la verificación del negocio en Meta y activar WhatsApp real;
   afinar la ventana exacta del throttle de OTP.
8. Tests del gateway FastAPI (webhook: firma, parseo, reenvío) y subir el job
   de CI de lint-only a tests.
9. Observabilidad mínima: Sentry (Django + Next) y healthchecks monitorizados.

### P2 — Completar el alcance funcional
10. UI de convenios y tarifarios en Configuración (backend ya listo).
11. App móvil de pacientes (Flutter): login OTP, citas, evoluciones visibles,
    estado de cuenta — el backend ya expone lo necesario.
12. Google Calendar Fase 2 (OAuth bidireccional).
13. Firma electrónica firmaEC (.p12) para recetas y consentimientos.

### P3 — Salud del código a mediano plazo
14. ESLint (+ eventual migración incremental a TypeScript) y tests de frontend
    (Playwright sobre los flujos del QA-CHECKLIST).
15. Trocear las páginas monolíticas del panel en componentes por pestaña.
16. Revisión de seguridad previa a escalar: almacenamiento de tokens, CSP,
    rate-limits por endpoint sensibles, dependencia `cryptography`/renovación
    de versiones (Django 5.0 sale de soporte extendido — planificar salto a LTS).

---

*Documento generado a partir del análisis del código en el Sprint 52. Antes de
implementar cualquier característica nueva, revisar la sección 4.2: varias
funcionalidades ya tienen implementación parcial o backend completo esperando UI.*
