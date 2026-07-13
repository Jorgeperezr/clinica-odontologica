# Sistema de Gestión — Clínica Odontológica

## Cómo correr los tests (comando canónico)

```bash
docker compose exec django-api python manage.py test --settings=config.settings_test
```

Descubrimiento automático de TODOS los tests — el mismo comando que ejecuta
el CI, de modo que el número local y el de GitHub Actions siempre coinciden.
**Referencia actual: 124 tests** (si agregas tests, actualiza este número en
el mismo commit para que sirva de verificación rápida).


Monorepo con dos servicios de backend independientes:

- **`django-api/`** — Backend principal (Django + Django REST Framework). Fuente de verdad de todo el dominio: usuarios, pacientes, agenda, historia clínica, tratamientos, pagos, inventario, reportes y configuración.
- **`whatsapp-gateway/`** — Microservicio (FastAPI) dedicado a la integración con WhatsApp Business Cloud API de Meta: envío de plantillas, verificación y procesamiento del webhook.

Ver la documentación completa de las 7 fases previas (PRD, SRS, Arquitectura, Modelo de datos, APIs, Backlog, Roadmap) en los documentos ya entregados.

## Estado actual: Sprint 25 completado — índices CPO-ceo y export PDF del formulario 033

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

### Sprint 2 — Cierre de Pacientes + catálogos de Configuración (hecho)
- **Especialidades:** catálogo ABM (RF-CFG-01), con las 5 base del SRS sembradas automáticamente por `bootstrap` (Clínica general, Ortodoncia, Endodoncia, Periodoncia, Odontopediatría).
- **Tratamientos:** catálogo ABM (RF-CFG-02) con especialidad y precio base, validando que la especialidad pertenezca a la misma clínica.
- **Convenios y tarifarios:** aseguradoras/empresas con descuentos, y precios por convenio (RF-CFG-03, RF-CFG-04).
- **Parámetros del sistema:** clave-valor (días de morosidad, ventana de recordatorio, stock mínimo, alerta de vencimiento), sembrados por `bootstrap` y editables solo por admin (RF-CFG-05).
- **Permisos:** escritura de configuración solo admin; lectura para todo el staff clínico.
- **Tests:** 9 tests nuevos (19 en total), incluyendo aislamiento entre clínicas y seed idempotente del bootstrap — todos en verde.

### Sprint 3 — Agenda (hecho)
- **Doctores:** perfil extendido del usuario (color de agenda, especialidades, preparado para token de Google Calendar).
- **Citas:** creación con validación de solapamiento por doctor y bloqueo de citas en el pasado (RF-AGN-03).
- **Estados:** pendiente, confirmada, cancelada, reagendada, completada, no asistió (RF-AGN-04).
- **Check-in / check-out** con marca de tiempo (RF-AGN-05).
- **Vista de agenda** diaria/semanal/mensual, filtrable por doctor; un doctor solo ve su propia agenda (RF-AGN-01, 02).
- **Reagendar / cancelar** con validación de conflictos.
- **Pendiente para sprints siguientes:** bloqueo por morosidad (Sprint 9, requiere billing); sincronización Google Calendar (OAuth2) y aviso de llegada por WhatsApp (Sprint 10).
- **Tests:** 8 nuevos (27 en total) — todos en verde.

### Sprint 4 — Historia clínica, parte 1 (hecho)
- **Historia clínica general** por paciente (RF-HCL-01).
- **Evoluciones** fechadas con tipo (nota clínica / receta / indicación de cuidado) y flag `visible_to_patient` que controla qué ve la app móvil (RF-HCL-03, RF-APP-03/04/06).
- **Diagnósticos** asociados a pieza dental (FDI) o generales (RF-HCL-04).
- **Planes de tratamiento** con secuencia de procedimientos, cada uno con estado (planificado/en progreso/realizado) (RF-HCL-05).
- **Auditoría explícita** de todo acceso a datos clínicos, incluso lectura (exigencia LOPDP / RNF-004).
- **Permisos:** solo roles clínicos (admin/doctor/auxiliar); recepción no accede a datos clínicos.
- **Pendiente para Sprints 5-6:** odontograma interactivo, radiografías, consentimientos con firma; descuento de inventario al completar un ítem (Sprint 11).
- **Tests:** 6 nuevos (33 en total) — todos en verde.

### Sprint 5 — Odontograma interactivo + fix de CI (hecho)
- **Catálogo de 12 estados dentales** parametrizable (sano, caries, obturado, corona, ausente, etc.), sembrado por `bootstrap` y editable desde el admin sin tocar código (RF-HCL-02, SRS 3.4.1).
- **Registro histórico** por pieza (FDI) y superficie — nunca se sobrescribe; cada cambio crea una fila nueva (trazabilidad clínica completa).
- **Vista "estado actual de la boca"** (`/odontogram/current/`): calcula el último estado por cada pieza/superficie para que el frontend dibuje el odontograma.
- **Auditoría** de todo acceso al odontograma.
- **Fix de CI (GitHub Actions):** corregidos 4 errores de lint, reescrito el workflow (usa SQLite en tests, sin Postgres service innecesario, secret key larga para evitar HMAC warning, gateway como lint-only hasta que tenga tests).
- **Tests:** 6 nuevos (39 en total) — todos en verde.

### Sprint 6 — Cierre del módulo clínico (hecho)
- **Consentimientos informados** con firma capturada en pantalla táctil (base64), generación de PDF con la firma incrustada usando reportlab, y registro de fecha/hora/IP como evidencia — registro interno según la legislación ecuatoriana (RF-HCL-07).
- **Radiografías y fotografías clínicas** asociadas a fecha y opcionalmente a pieza dental (RF-HCL-06).
- **Exportación de la historia clínica completa a PDF** (diagnósticos, evoluciones, planes) (RF-HCL-08).
- **Validación robusta:** firmas ilegibles o base64 inválido se rechazan sin romper la generación del PDF.
- **Tests:** 4 nuevos (43 en total) — todos en verde.
- **Bug corregido:** `status` no estaba importado en la vista de firma, lo que habría causado un crash en producción al recibir una firma inválida.

### Sprint 7 — Formularios por especialidad + fix JWT blacklist (hecho)
- **Formularios clínicos por especialidad** (Ortodoncia, Endodoncia, Periodoncia, Odontopediatría) usando JSONField flexible: el doctor puede registrar campos base sugeridos o personalizados sin requerir cambios de código (RF-ESP-01, RF-ESP-02).
- **Plantillas de campos** por especialidad, expuestas vía `/specialties/{id}/form-template/` para que el frontend sepa qué mostrar. Ajustables sin migraciones.
- **Multi-especialidad:** un paciente puede tener formularios de varias especialidades simultáneamente (RF-ESP-03).
- **Fix (detectado en revisión de arquitectura):** faltaba `rest_framework_simplejwt.token_blacklist` en INSTALLED_APPS. Sin él, la rotación de tokens y el logout no invalidaban tokens de verdad. Corregido y verificado (aplica sus migraciones).
- **Tests:** 6 nuevos (49 en total) — todos en verde.

### Sprint 8 — Tratamientos y pagos (hecho)
- **Presupuestos** con líneas de tratamiento; el total se recalcula automáticamente al agregar ítems (RF-TRP-01).
- **Aprobación** de presupuestos y conversión a **plan de pago en cuotas mensuales** (RF-TRP-02). El reparto de centavos es exacto: la última cuota absorbe el redondeo para que la suma sea siempre el total.
- **Registro de cobros** parciales o totales; una cuota se marca como pagada solo cuando su saldo llega a cero (RF-TRP-03).
- **Estado de cuenta** del paciente: total, pagado, saldo y detección de cuotas vencidas (RF-TRP-04) — esto es lo que el Sprint 9 usará para el bloqueo por morosidad.
- **Honorarios por doctor** (porcentaje o monto fijo) (RF-TRP-05).
- **Tests:** 9 nuevos (58 en total), incluyendo el reparto exacto de centavos y pagos parciales — todos en verde.

### Sprint 9 — Cierre financiero + bloqueo por morosidad (hecho)
- **Bloqueo por morosidad activo** (RF-AGN-07 / RN-AGN-01): al crear una cita, el backend verifica si el paciente tiene cuotas vencidas más allá del umbral configurable (`dias_morosidad`). Si es moroso, devuelve 409; admin/recepción pueden forzar con `override=true` (excepción manual). La regla vive en el backend, aplica igual desde web o app.
- **Lógica de morosidad centralizada** (`billing/services.py`): una sola definición de "paciente moroso" usada por agenda, reportes y la tarea programada.
- **Reportes:** financiero (ingresos por método de pago), morosidad (quién debe, cuánto, desde cuándo), producción por doctor (RF-REP-01/02/03, RF-TRP-06).
- **Tarea Celery diaria** (`mark_overdue_installments`) que marca automáticamente las cuotas vencidas — programada vía Celery Beat a las 00:30.
- **Tests:** 8 nuevos (66 en total), incluyendo bloqueo, override, umbral configurable, cuota pagada que no bloquea, y la tarea de vencimiento — todos en verde.

### Sprint 10 — Automatización WhatsApp (hecho, modo simulado)
- **Tareas de mensajería** (Celery): recordatorios de cita (según ventana configurable), recordatorios de pago, aviso de llegada del paciente al doctor. OTP ya existía del Sprint 1.
- **Opt-in del paciente** (RN-WSP-02): registro de consentimiento con canal y fecha; los mensajes solo se envían a pacientes con opt-in activo (exigencia de Meta y LOPDP).
- **Webhook de Meta completado** (lado FastAPI): parseo real de eventos — estados de entrega (sent/delivered/read/failed) y mensajes entrantes. Una respuesta afirmativa del paciente confirma su cita automáticamente (RF-WSP-03).
- **Gestión de plantillas** de WhatsApp (RN-WSP-01).
- **Celery Beat:** recordatorios de cita cada hora, recordatorios de pago diarios.
- **Modo simulado:** sin credenciales de Meta, el gateway simula el envío. Cuando la verificación de negocio en Meta esté aprobada, solo hay que poner las credenciales en el `.env` — no requiere cambios de código.
- **Bugs corregidos:** firma incorrecta de `has_permission` en el endpoint interno (habría roto en runtime); import perdido de `notify_django` en el gateway; check-in ahora resiliente a fallos del broker Celery.
- **Tests:** 6 nuevos (72 en total) — todos en verde.

### Sprint 11 — Inventario + reportes finales (hecho) — BACKEND COMPLETO
- **Inventario:** productos con stock mínimo, lotes con fecha de vencimiento, historial de movimientos (RF-INV-01/02).
- **Alertas:** stock bajo (RF-INV-03) y lotes próximos a vencer con días configurables (RF-INV-04).
- **Descuento automático de stock** al marcar un tratamiento como realizado, usando FEFO (primero el lote que vence antes) y registrando el consumo (RF-INV-05). Conecta historia clínica ↔ inventario.
- **Reportes finales:** pacientes nuevos e inventario, con **exportación a Excel** (openpyxl) (RF-REP-04/05/06).
- **Bug corregido:** el parámetro `format` colisionaba con la negociación de contenido de DRF (daba 404); renombrado a `export`.
- **Tests:** 8 nuevos (80 en total) — todos en verde.

## 🎉 Backend completo (Sprints 0-11)
Los 11 módulos del sistema están implementados y probados: usuarios, pacientes, agenda, historia clínica, odontograma, especialidades, tratamientos/pagos, inventario, WhatsApp, reportes y configuración. **80 tests, CI verde.** Siguiente fase: frontend (panel web Next.js) y app móvil Flutter.

### Sprint 12 — Frontend web: fundaciones (hecho)
- **Proyecto Next.js 14** (`frontend/`) con export estático para producción y servidor de desarrollo en Docker (puerto 3000).
- **Sistema de diseño propio:** paleta petrol/menta (identidad dental sin el azul-hospital genérico), tokens CSS, números tabulares para montos y cédulas, foco visible y movimiento reducido (accesibilidad).
- **Login** con JWT contra la API Django, manejo de errores y refresh automático de tokens.
- **Panel protegido** con navegación lateral filtrada por rol (matriz del SRS): recepción no ve reportes, auxiliar no ve pagos, etc.
- **Módulo de Pacientes:** listado con búsqueda (nombre/cédula), registro de pacientes con validación.
- **Detección automática de la URL del backend en Codespaces** (puerto 3000 → 80) sin configuración manual.

### Sprint 13 — Agenda visual (hecho)
- **Vista de agenda día/semana** con navegación de fechas (←/hoy/→), filtro por doctor y estados con color (pendiente/confirmada/completada/cancelada/no asistió).
- **Creación de citas** con búsqueda de paciente en vivo (nombre o cédula), selección de doctor, fecha y horario. Las validaciones del backend (solapamiento, citas en pasado) se muestran como mensajes claros.
- **Bloqueo por morosidad integrado en la UI:** si el backend devuelve 409 `patient_delinquent`, el panel muestra la advertencia y ofrece la excepción manual (`override`) con un clic — el flujo completo RF-AGN-07 de punta a punta.
- **Acciones por estado:** Confirmar/Cancelar (pendiente), Llegó = check-in (confirmada), Finalizar = check-out (en atención). El check-in dispara el aviso WhatsApp al doctor (Sprint 10).

### Sprint 14 — Ficha del paciente + odontograma interactivo (hecho)
- **Ficha del paciente** (clic en cualquier fila del listado): cabecera con datos, pestañas de Odontograma y Evoluciones.
- **Odontograma FDI interactivo (SVG):** 32 piezas en 4 cuadrantes, cada una pintada con el color del estado actual del catálogo. Clic en una pieza → panel para registrar un nuevo estado (histórico, nunca sobrescribe) + historial completo de esa pieza con fechas y colores. La firma visual del sistema (RF-HCL-02).
- **Leyenda del catálogo** de 12 estados con sus colores (parametrizable desde el admin).
- **Evoluciones:** registro de notas clínicas / recetas / indicaciones con el flag "visible para el paciente" (lo que la app móvil mostrará), y listado con doctor y tipo.
- **Fix:** `Doctor.full_name` devolvía el email (quedó del Sprint 3, cuando User no tenía nombre); ahora usa el nombre real con email de respaldo.

### Sprint 15 — Pagos en el panel (hecho)
- **Búsqueda de paciente** y su **estado de cuenta** en tarjetas: total, pagado, saldo y cuotas vencidas (la tarjeta se pinta en rojo si hay morosidad).
- **Presupuestos:** creación, ítems desde el catálogo de tratamientos (el precio se pre-carga desde el tarifario y es editable), total autocalculado, aprobación con confirmación.
- **Plan de cuotas:** número de cuotas y primera fecha; el reparto exacto de centavos del Sprint 8, ahora visible.
- **Cobros:** formulario inline por cuota (monto editable para pagos parciales + método efectivo/transferencia/tarjeta); la cuota pasa a Pagada cuando el saldo llega a cero.
- **Backend:** `payment_plan_id` expuesto en el serializer de presupuestos para enlazar presupuesto → cuotas.

### Sprint 16 — Inventario, Reportes y Configuración en el panel (hecho) — PANEL WEB COMPLETO
- **Inventario:** productos con badge de stock bajo, alertas visibles (stock bajo + lotes por vencer en 30 días con días restantes en color), registro de productos y de lotes (cada lote genera su movimiento de entrada).
- **Reportes (admin):** ingresos del período con desglose por método de pago, producción por doctor, tabla de morosidad (monto, cuotas, días, si bloquea agendamiento) y pacientes nuevos — con rango de fechas y **descarga a Excel** (pacientes e inventario).
- **Configuración (admin):** pestañas de Tratamientos (crear con especialidad y precio base — alimenta los presupuestos), Especialidades, y Parámetros del sistema con edición inline (morosidad, recordatorios, alertas) con nombres legibles.

## 🎉 Panel web completo (Sprints 12-16)
Los 7 módulos de la barra lateral funcionan de punta a punta contra la API: Inicio, Pacientes (con ficha + odontograma interactivo), Agenda (con morosidad), Pagos (presupuestos → cuotas → cobros), Inventario, Reportes y Configuración. Pendiente del Roadmap: app móvil de pacientes (Flutter), QA integral y despliegue (Fase 12).

### Sprint 17 — QA integral (hecho)
- **Prueba end-to-end** (`apps/common/tests_e2e.py`): simula el flujo completo de una clínica a través de TODOS los módulos en un solo test — registro de paciente, opt-in, catálogo, presupuesto con plan de cuotas vencidas, bloqueo por morosidad + override, cobro total, desbloqueo verificado, atención (confirmar/check-in/evolución/odontograma/check-out), descuento automático de inventario, reportes que reflejan todo, y exports Excel/PDF. Pasó a la primera: el sistema integra correctamente.
- **CI ampliado:** nuevo job `frontend-build` que compila el panel Next.js en cada push — un cambio que rompa el build ya no llega a main sin aviso.
- **`QA-CHECKLIST.md`:** checklist de QA manual de la UI (roles, flujos, robustez) para recorrido sistemático en el navegador.
- **Tests:** 91 en total (90 + E2E) — todos en verde.

### Sprint 18 — Fase 12: preparación para producción (hecho)
- **Settings endurecidos** (activos con `DEBUG=False`): cookies seguras, X-Frame DENY, nosniff, HSTS configurable, soporte de proxy TLS (X-Forwarded-Proto) — verificado con `check --deploy`.
- **`docker-compose.prod.yml`:** imágenes inmutables (sin --reload ni volúmenes de código), Postgres/Redis sin puertos expuestos, panel compilado a estático y servido por Nginx, restart automático.
- **`.env.production.example`:** plantilla con todos los valores a cambiar e instrucciones para generar la SECRET_KEY.
- **`DEPLOY.md`:** comparativa de hosting (VM GCP vs PC + Cloudflare Tunnel) con pasos concretos por opción, backups con pg_dump + destino externo, procedimiento de actualización y checklist pre-pacientes-reales.
- **Frontend:** `apiBase()` detecta producción (mismo origen vía Nginx) además de Codespaces y dev local.

### Sprint 19 — SaaS multi-tenant con Super Administrador (hecho)
Jerarquía: **Super Administrador** (plataforma, sin clínica) → **Clínicas** (tenants) → staff de cada clínica (admin, doctores, recepción, auxiliares).
- **Rol `superadmin`** (sin tenant) + comando `python manage.py createsuperadmin --email … --password …` para crear el primero.
- **Panel de Plataforma** (`/panel/plataforma/`, solo superadmin): indicadores globales, crear clínicas (con siembra automática del catálogo: especialidades, parámetros, 12 estados de odontograma), crear el Administrador inicial de cada clínica, y activar/desactivar clínicas.
- **Desactivación efectiva:** autenticación tenant-aware — al desactivar una clínica, sus usuarios pierden acceso al instante aunque tengan tokens vigentes (los datos no se borran).
- **Aislamiento verificado por tests:** el staff de la Clínica A no puede listar NI leer por ID datos de la Clínica B (98 tests en total, 7 nuevos de plataforma, incluyendo el test de aislamiento).
- El middleware de auditoría ahora soporta acciones de plataforma (sin tenant).

### Sprint 20 — Agenda avanzada: mes, flujo de atención, calendario y recordatorios (hecho)
- **Vista mensual:** cuadrícula del mes con conteo de citas por día (hoy resaltado); clic en un día abre su agenda en detalle. Backend `mode=monthly`.
- **Flujo de atención completo:** Llegó (check-in, chip "En espera") → **Iniciar atención** (nuevo, chip "En atención") → Finalizar. Con validaciones (no se puede iniciar sin check-in, ni dos veces).
- **Google Calendar Fase 1 (funciona hoy, sin credenciales):** feed iCalendar por doctor con URL secreta (botón "🗓 Calendario del doctor" en Agenda). Google/Apple/Outlook se suscriben y las citas aparecen y se actualizan solas en el calendario personal del dentista. La Fase 2 (bidireccional con OAuth) queda documentada en DEPLOY.md; `google_calendar_event_id` ya existe en el modelo.
- **Recordatorios WhatsApp con confirmación:** ya existían del Sprint 10 (webhook entiende "CONFIRMO"/"sí" y confirma la cita). Este sprint: **fix de un bug real** — la tarea no marcaba las citas recordadas y habría enviado ~24 recordatorios por cita; ahora `reminder_sent_at` garantiza uno solo, la plantilla incluye la instrucción de confirmación, y la agenda muestra 📨 en las citas ya recordadas.

### Sprint 21 — Panel de Plataforma v2 (según especificación) (hecho)
El Super Administrador SOLO administra la plataforma — nunca la información operativa de las clínicas (verificado por test: los endpoints de pacientes/citas/reportes/inventario le devuelven 403).
1. **Dashboard:** clínicas registradas / activas / suspendidas + total de administradores de clínica.
2. **Gestión de Clínicas:** registrar y editar datos generales (nombre, RUC, dirección, teléfono, correo), activar/suspender (con efecto inmediato sobre las sesiones), estado visible.
3. **Administradores de Clínicas:** solo el admin principal de cada una — crear, **restablecer contraseña** (temporal generada, se muestra UNA sola vez), activar/desactivar la cuenta, actualizar correo.
4. **Auditoría:** solo las acciones del propio Super Administrador (crear/editar/suspender clínica, credenciales, configuración), con fecha, usuario y detalle.
5. **Configuración General:** nombre y logo de la plataforma, SMTP (contraseña nunca se expone en la API), zona horaria y moneda.
- **Fixes:** el GET del listado de clínicas fallaba (FieldError del Sprint 19, ahora con test de regresión); las clínicas nuevas nacen siempre activas; parseo booleano robusto.

### Sprint 22 — Historia clínica avanzada (hecho)
Las 5 características del paquete:
1. **Planes con plantillas, presupuesto automático y progreso:** plantillas de planes (Configuración → Plantillas de plan: armar "Ortodoncia completa" con tratamientos del tarifario); en la ficha se aplican con un clic (crea el plan con precios), barra de progreso por ítems realizados, y botón "Generar presupuesto" que arma el presupuesto de billing desde el plan.
2. **Diario clínico con línea de tiempo y alertas de seguimiento:** las evoluciones aceptan fecha de seguimiento; el dashboard muestra "Seguimientos pendientes" (con días de atraso, clic → ficha) para doctores/admin/auxiliares.
3. **Documentos y fotos por paciente:** pestaña Documentos en la ficha — subir radiografías, fotos clínicas, exámenes, informes, identificación, órdenes y referencias, con galería de imágenes y filtros por categoría (RF-PAC-04).
4. **Recetas profesionales:** PDF A5 con membrete de la clínica, datos del doctor con registro profesional y **firma manuscrita estampada** (los doctores la dibujan en "Mi firma", con dedo o mouse). firmaEC legal = Fase 2 (requiere el certificado .p12 de cada doctor — DEPLOY.md).
5. **Consentimientos con firma táctil:** pestaña Consentimientos en la ficha — el paciente firma con el dedo en la pantalla (tablet/teléfono/mouse), se genera el PDF con la firma incrustada, fecha/hora e IP (RF-HCL-07, ahora con UI completa).
- Fixes: plantillas nacen activas (checkbox semantics); precio base en ítems de plantilla.

### Sprint 23 — Formulario MSP HCU-033/2021, parte 1 (hecho)
Alineación de la historia clínica con el formulario oficial del Ministerio de Salud Pública del Ecuador.
- **Odontograma ampliado a 22 estados** según la simbología oficial (literal K): sellante necesario/realizado, endodoncia por realizar/realizada, corona indicada/realizada, prótesis fija/removible/total indicada/realizada, pérdida por caries/otra causa, etc. (residuo de intentos previos, consolidado y con tests actualizados).
- **Panel Form 033 en la pestaña Odontograma** (`lib/Form033Panel.js`): literales B (motivo de consulta + embarazo), C (enfermedad actual), D (antecedentes personales — 10 opciones oficiales), E (antecedentes familiares — 10 oficiales), F (constantes vitales), G (examen estomatognático — 13 regiones oficiales). Registro por consulta con historial desplegable.
- **Literal O automático:** los datos del profesional (nombre, registro, fecha/hora) se guardan solos desde la credencial autenticada y no se muestran como formulario.
- **Catálogo CIE-10 odontológico sembrado** (~90 códigos K00–K14 + S02.5, S03.2, Z01.2, Z29.8) con búsqueda por código o nombre (base del literal N).
- `sex` añadido al paciente (literal A); campos de movilidad/recesión en el registro de pieza (literal H).

### Sprint 24 — Formulario MSP HCU-033/2021, parte 2 (hecho)
- **Literal N — Diagnósticos CIE-10** (`lib/DiagnosisTab.js`): en la pestaña Odontograma, el profesional busca por código o nombre (buscador con debounce contra el catálogo sembrado), elige pieza y marca **PRE (presuntivo)** o **DEF (definitivo)**. El serializer ahora expone `diagnosis_kind`/`kind_display`.
- **Literales L / M — Exámenes complementarios** (`lib/ExamRequestsSection.js`): en la pestaña Documentos, se piden exámenes (biometría, química, rayos X, otros) y se carga su informe. Estado pendiente → con informe.
- **Leyenda del odontograma** con los 22 estados oficiales (se arma sola desde el catálogo).

### Sprint 25 — Índices J (CPO-ceo) + export del formulario 033 a PDF (hecho)
- **Literal J — Índices CPO-ceo** (`lib/CpoCeoCard.js` + endpoint `GET /patients/{id}/cpo-ceo/`): calculados automáticamente desde el odontograma. CPO para dientes permanentes (FDI 11-48) y ceo para temporales (FDI 51-85). C/c = cariados · P/e = perdidos o con extracción indicada · O/o = obturados o con corona. Tarjeta con las dos tablas en la pestaña Odontograma, recalculada al registrar estados.
- **Export del formulario 033 a PDF oficial** (`form033_pdf.py` + endpoint `GET /patients/{id}/form033/export-pdf/`): reúne los literales A-O del paciente (datos, motivo, enfermedad actual, antecedentes, vitales, examen estomatognático, índices CPO-ceo, diagnósticos CIE-10 y datos del profesional) en un PDF imprimible con las bandas de título del formato oficial. Botón "⬇ Exportar formulario 033 (PDF)" en la tarjeta de índices.

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
