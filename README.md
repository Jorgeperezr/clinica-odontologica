# Sistema de Gestión — Clínica Odontológica

## Cómo correr los tests (comando canónico)

```bash
docker compose exec django-api python manage.py test --settings=config.settings_test
```

Descubrimiento automático de TODOS los tests — el mismo comando que ejecuta
el CI, de modo que el número local y el de GitHub Actions siempre coinciden.
**Referencia actual: 132 tests** (si agregas tests, actualiza este número en
el mismo commit para que sirva de verificación rápida).


Monorepo con dos servicios de backend independientes:

- **`django-api/`** — Backend principal (Django + Django REST Framework). Fuente de verdad de todo el dominio: usuarios, pacientes, agenda, historia clínica, tratamientos, pagos, inventario, reportes y configuración.
- **`whatsapp-gateway/`** — Microservicio (FastAPI) dedicado a la integración con WhatsApp Business Cloud API de Meta: envío de plantillas, verificación y procesamiento del webhook.

Ver la documentación completa de las 7 fases previas (PRD, SRS, Arquitectura, Modelo de datos, APIs, Backlog, Roadmap) en los documentos ya entregados.

## Arranque en Codespaces (tras reiniciar)

Un solo comando deja todo listo (crea el `.env`, escribe las URLs de este
Codespace, pone los puertos 80 y 3000 en Public, levanta los contenedores
y aplica migraciones):

```bash
bash scripts/start-codespace.sh
```

Es idempotente: se puede correr las veces que haga falta. Si el login da
"Failed to fetch", casi siempre es que los puertos 80 y 3000 volvieron a
Private — el script los corrige, o se hacen Public a mano en la pestaña
PORTS (clic derecho → Port Visibility → Public).

### Persistencia de los datos en Codespaces

Los datos de Postgres viven en `./data/postgres` (bind mount al workspace),
no en un volumen de Docker. Motivo: en Codespaces el daemon de Docker corre
dentro del dev container, así que **"Rebuild Container" borra todos los
volúmenes de Docker** — y con ellos la base de datos. `/workspaces` en
cambio persiste entre reinicios y rebuilds.

`data/` y `backups/` están en `.gitignore`: **nunca deben subirse al
repositorio** (contienen datos de pacientes).

Si aun así la base queda vacía (por ejemplo al recrear el Codespace desde
cero), `scripts/start-codespace.sh` lo detecta y crea la clínica y los
usuarios de desarrollo automáticamente.

## Estado actual: Sprint 60 — motor global de estilos de documentos (base)

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

### Sprint 26 — Odontograma oficial MSP con superficies (hecho)
Reemplazo de la representación gráfica del odontograma por la del formulario HCU-033/2021, conservando toda la lógica de negocio (el backend ya soportaba superficies e movilidad/recesión).
- **Distribución oficial exacta:** permanente superior (18-11 | 21-28), temporal superior (55-51 | 61-65), temporal inferior (85-81 | 71-75), permanente inferior (48-41 | 31-38).
- **5 superficies clicables por pieza** (`lib/Odontogram.js` reescrito): cada diente permanente es un cuadrado con rombo interior (vestibular, palatina/lingual, mesial, distal, oclusal central); los temporales son círculos con las mismas 5 caras. Cada superficie se pinta con el color del estado vigente de esa cara y se marca por separado.
- **Recesión y movilidad por pieza:** casillas sobre y bajo cada arcada (valores 1-4), como en el formulario. Se guardan por pieza en el ToothRecord.
- **Lógica intacta:** selección de pieza y superficie, registro de estados, historial por pieza, notas, eliminación auditada, actualización automática e índices CPO-ceo siguen funcionando igual. Colores y catálogo de 22 estados sin cambios.
- Responsive con scroll horizontal en pantallas angostas.

### Sprint 27 — Usabilidad: ordenamiento, vistas y layout responsive (hecho)
Mejoras de UX sin tocar la lógica de negocio.
- **Ordenamiento del listado de pacientes** (`?ordering=`): nombre A-Z / Z-A, fecha de registro (recientes/antiguos), número de atenciones (mayor/menor) y próxima cita según la agenda. El backend anota `attention_count` (Count de citas) y `next_appointment` (Min de citas futuras) sin alterar el flujo existente; un ordering inválido cae a nombre A-Z.
- **Vista de lista o de tarjetas** en Pacientes: toggle con preferencia recordada; las tarjetas muestran avatar con iniciales, teléfono, nº de atenciones y próxima cita. La lista suma las columnas de atenciones y próxima cita.
- **Menú lateral contraíble** (`layout.js`): botón «/» que colapsa el sidebar a solo iconos (64px) o lo expande (220px), con la preferencia recordada. Los ítems muestran icono + tooltip cuando está colapsado.
- **Contenido principal responsive:** el panel blanco ocupa todo el ancho restante, se centra automáticamente (maxWidth 1200) y usa padding fluido (`clamp`), adaptándose al colapso del menú y a cualquier resolución sin espacios vacíos.

### Sprint 28 — Literales I, J y K del formulario MSP 033 (hecho)
Completa las tres secciones que rodean al odontograma en el formulario oficial, 100% frontend (el backend ya tenía los campos).
- **I. Indicadores de Salud Bucal** (`lib/OralHealthIndicators.js`): higiene oral simplificada (placa 0-3, cálculo 0-3, gingivitis 0-1 por las 6 piezas índice, con totales), enfermedad periodontal (leve/moderada/severa), tipo de oclusión (Angle I/II/III) y nivel de fluorosis (leve/moderada/severa). Se guarda en el campo `indicadores_salud_bucal` del Form033.
- **J. Índices CPO-ceo** (`lib/CpoCeoCard.js` rediseñado): mismo formato del formulario oficial — filas D (permanentes: C-P-O-Total) y d (temporales: c-e-o-Total), con las etiquetas en menta y los totales en durazno. Se siguen calculando automáticamente desde el odontograma.
- **K. Simbología del odontograma** (`lib/OdontogramLegend.js`): reemplaza la leyenda de cuadros de color por los símbolos oficiales del MSP (círculo relleno = caries/obturado, X = extracción/pérdida, triángulo = endodoncia, cuadrado con punto = corona, líneas = prótesis total, A = ausente, rayo = fractura, etc.), mapeados por código de estado. La lógica de los 22 estados no cambia.

### Sprint 29 — Export 033 completo + limpieza de textos (hecho)
- **Export del formulario 033 ampliado** (`form033_pdf.py` + endpoint): el PDF ahora reúne TODA la información del paciente — datos, motivo, enfermedad actual, antecedentes, vitales, examen estomatognático, indicadores de salud bucal, índices CPO-ceo, diagnósticos CIE-10, plan de tratamiento (con estado por ítem), exámenes complementarios con su informe, documentos adjuntos y consentimientos (firmado/pendiente), más los datos del profesional. Con salto de página automático para que nada se corte.
- **Títulos sin literales:** se quitaron las referencias A-P de todas las pestañas y secciones ("Historia clínica MSP — Form.033/2021 (literales…)" → "Historia clínica odontológica", "J. Índices CPO-ceo" → "Índices CPO-ceo", "N. Diagnósticos" → "Diagnósticos", etc.). Nombres funcionales orientados al usuario.
- **Textos más naturales:** mensajes e instrucciones reescritos en lenguaje clínico claro y breve, sin jerga técnica ni frases que suenen generadas por máquina.

### Sprint 30 — Correcciones, reportes mejorados e interacción del odontograma (hecho)
Sin cambios de backend (los 132 tests no varían).
- **Correcciones:** eliminados los 3 diálogos nativos que quedaban (el `prompt` de recesión/movilidad, el `alert` de la URL del calendario en Agenda y el `prompt` de correo en Plataforma — ahora todo es edición inline consistente con el resto del sistema); import muerto en `CpoCeoCard` y elemento SVG residual en el odontograma eliminados. El script de arranque ya no compite con el `migrate` del contenedor (espera el "Listening at" de gunicorn — corrige el error "relation already exists").
- **Odontograma más interactivo:** la superficie seleccionada queda resaltada en petrol dentro del diente; hover con atenuación y borde sobre cada superficie; y el registro de **recesión/movilidad** ahora es un editor inline bajo el odontograma con botones 1-4, "Borrar valor" y "Cancelar" (el valor actual aparece marcado).
- **Reportes con mejor formato:** rangos rápidos (Hoy / Este mes / Mes pasado / Este año), etiqueta del período legible, **barras proporcionales** en ingresos por método y producción por doctor, **total vencido** en morosidad con filas accionables (clic → ficha del paciente) y resaltado rojo para quienes ya bloquean, botón **Imprimir** con hoja de estilos de impresión (oculta menú y controles), y estado de carga.

### Sprint 31 — Formulario oficial autocompletado + indicador de citas (hecho)
- **Autocompletado del formulario OFICIAL del MSP (Excel):** además del PDF, ahora se puede descargar la plantilla oficial del Ministerio (`apps/clinical/resources/hcu_form033.xlsx`) rellenada con los datos del sistema — datos del paciente, motivo, embarazo, enfermedad actual, constantes vitales, índices CPO-ceo, diagnósticos CIE-10 (PRE/DEF) y datos del profesional. Nuevo endpoint `patients/<pk>/form033/export-xlsx/` y `apps/clinical/form033_xlsx.py`. El generador respeta las celdas combinadas de la plantilla y anexa cada valor bajo su etiqueta sin destruir el formato; los totales CPO-ceo se dejan como fórmulas de la plantilla. En la ficha, botón "Formulario oficial MSP (Excel)" junto al de PDF.
- **Nuevo indicador de reportes — Actividad de citas:** endpoint `reports/appointments-summary/` con total de citas del período, desglose por estado (completadas, confirmadas, pendientes, canceladas, no asistió), tasa de asistencia (completadas / [completadas + no asistió]) y tasa de cancelación. Tarjeta en Reportes con la tasa de asistencia coloreada (verde ≥ 80 %).

### Sprint 32 — Registro por simbología (flujo profesional) (hecho)
100% frontend; la lógica de negocio y la estructura de datos no cambian.
- **La Simbología del Odontograma es ahora el mecanismo de registro:** se selecciona la pieza o superficie en el odontograma (la superficie se detecta automáticamente al hacer clic) y luego se hace clic en el símbolo del estado en la leyenda. Los símbolos son botones con hover; una guía sobre la leyenda indica el paso siguiente ("Pieza 16 seleccionada — haz clic en un símbolo…").
- **Mini-formulario emergente** al elegir el símbolo: muestra el estado y la pieza, la superficie autocompletada (editable en un desplegable) y notas opcionales; Guardar (o Enter) registra de inmediato. Sin diálogo de confirmación adicional: pieza → símbolo → guardar, tres clics.
- **Panel lateral eliminado:** ya no aparece el listado de botones de estados; el historial por pieza pasa a ancho completo y conserva su funcionamiento exacto (fecha, estado, superficie, notas, eliminación auditada).

### Sprint 33 — Atajo "Toda la pieza" + personalización visual por clínica (hecho)
- **Atajo "Toda la pieza":** clic en el número de cualquier pieza del odontograma la selecciona completa; además, al seleccionar una superficie aparece un chip "Pieza 16 · Oclusal" con el botón "Toda la pieza" para cambiar de modo al instante. Ambos modos de trabajo (superficie o pieza completa) conviven y el mini-formulario sigue permitiendo ajustar la superficie antes de guardar.
- **Configuración → Personalización (nuevo):** subir/cambiar/eliminar el logotipo de la clínica con vista previa; el logo aparece en la barra lateral. Modelo `ClinicBranding` (uno por tenant, migración `configuration/0005`), endpoint `config/branding/` (lectura para todos los roles del tenant, escritura solo admin).
- **Tema automático desde el logotipo:** al subirlo, el backend extrae los colores predominantes con Pillow (cuantización + filtro de fondos y grises) y ofrece "Usar como tema" con la paleta detectada.
- **Temas y personalización manual:** 6 temas predefinidos (Petróleo, Océano, Bosque, Vino, Grafito, Arena), selectores de color principal y secundario, y "Restablecer tema del sistema".
- **Accesibilidad garantizada:** el color primario se oscurece automáticamente hasta contrastar ≥ 4.5:1 (WCAG AA) con el texto blanco; el tono suave se genera claro para fondos. Como toda la interfaz pinta con variables CSS (`--petrol`, `--petrol-deep`, `--petrol-soft`, `--mint`), la barra lateral, botones, enlaces, pestañas activas, indicadores y tarjetas se re-tiñen solos (`lib/theme.js`).
- **Persistencia por clínica:** cada tenant guarda su logo y tema sin afectar a los demás (test de aislamiento incluido).

### Sprint 34 — Correcciones de Personalización: logo visible, recorte y nombre de la clínica (hecho)
- **Causa raíz del logo invisible corregida:** ni nginx proxyaba `/media/` ni Django lo servía, así que la URL del logotipo devolvía 404. Ahora `nginx.conf` proxya `/media/` y `/static/` hacia Django, y `config/urls.py` sirve media en desarrollo. El logo configurado por fin se ve; el icono predeterminado solo aparece si no hay logotipo.
- **Vista previa y recorte antes de guardar** (`lib/LogoCropper.js`): al elegir un archivo se muestra al instante, completo y con su relación de aspecto; un área de recorte se mueve arrastrando y se redimensiona por la esquina (eventos pointer: mouse y táctil), con "Usar imagen completa" o "Recortar y guardar" (genera un PNG solo con la zona elegida). La vista previa guardada muestra exactamente el archivo que usa la plataforma.
- **Nombre comercial y nombre corto** por clínica (migración `configuration/0006`): reemplazan el texto "Clínica" en la barra lateral (el corto tiene prioridad por espacio), el título de la ventana y el favicon usa el logotipo.
- **Identidad en vivo y por tenant:** al iniciar sesión cada clínica carga su logo, nombre, paleta y favicon (con caché local para pintado instantáneo); al guardar cambios en Personalización, la barra lateral y el favicon se actualizan al momento sin recargar (evento `branding:updated`).

### Sprint 35 — Logo transparente e iconos de línea (hecho)
100% frontend, sin cambios de backend (la suite no varía).
- **Logo con fondo transparente:** se quitó el recuadro blanco detrás del logotipo en la barra lateral, así los PNG con transparencia se integran con el color del sidebar. En la vista previa de Personalización el fondo es a cuadros (checkerboard) para que se note la transparencia real del archivo.
- **Iconos de línea profesionales** (`lib/NavIcons.js`): los glifos de texto del menú (⌂ ☺ ▤ $ ▦ ▨ ⚙ ◫) se reemplazaron por iconos SVG stroke de 24×24 con trazo redondeado (Inicio, Pacientes, Agenda, Mi firma, Pagos, Inventario, Reportes, Configuración, Plataforma). Usan `currentColor`, así que se re-tiñen solos con el tema de la clínica y el estado activo.

### Sprint 36 — Solicitud de examen complementario en PDF (hecho)
- **Formulario "Pedir examen" ampliado:** además de tipo y examen, ahora registra motivo/justificación clínica, observaciones (opcional) y prioridad (Normal/Urgente). El pedido se guarda con estado inicial "Pendiente" y aparece en la tabla con su prioridad (badge rojo si es urgente). Campos nuevos en `ExamRequest` (migración `clinical/0009`).
- **Acción "Generar PDF" por solicitud:** documento formal listo para imprimir o entregar, regenerable en cualquier momento (`apps/clinical/exam_request_pdf.py`, endpoint `patients/<pk>/exam-requests/<id>/pdf/`). Diseño profesional: encabezado con logotipo y datos de la clínica, datos del profesional (nombre, especialidad, registro y firma manuscrita si existe — todo desde la sesión autenticada), datos del paciente (nombre, identificación, edad calculada, sexo, historia clínica), detalle de la solicitud (fecha/hora, tipo, motivo, observaciones, prioridad), espacio para firma y sello, y pie institucional.
- **Datos de contacto de la clínica** (dirección, teléfono, correo) configurables en Personalización y usados en el encabezado y pie del PDF. Campos nuevos en `ClinicBranding` (migración `configuration/0007`).

### Sprint 37 — Consentimientos informados mejorados (hecho)
- **Bug de descarga corregido:** el botón "PDF firmado" abría `href={pdf_file}` (URL con localhost → ERR_CONNECTION_REFUSED, mismo problema que el logo). Ahora usa el mismo mecanismo que la solicitud de examen: `api()` + `blob()` + `window.open`. El PDF se genera, visualiza, descarga e imprime correctamente.
- **PDF profesional** (`apps/clinical/consent_pdf.py`, endpoint `consents/<id>/pdf/`, regenerable): encabezado con logo y datos de la clínica; datos del paciente (nombre, identificación, nacimiento, edad, sexo, HC); datos del profesional desde la sesión (nombre, especialidad, registro, firma); secciones (procedimiento, beneficios, riesgos, alternativas, declaración, observaciones); firmas de paciente y profesional con lugar/fecha y espacio para huella; pie institucional.
- **Plantillas reutilizables** (`ConsentTemplate`, migración `clinical/0010`): clasificadas por procedimiento (extracción, endodoncia, restauración, profilaxis, cirugía, implante, prótesis, ortodoncia). CRUD completo en Configuración → Consentimientos; al crear un consentimiento se puede partir de una plantilla y editarla antes de guardar.
- **Flujo de estados:** borrador → pendiente de firma → firmado → anulado. Un consentimiento firmado es inmutable (sólo puede anularse); historial de auditoría por consentimiento (`ConsentAuditLog`); el PDF definitivo se genera al firmar. Migración de datos `clinical/0011` preserva el estado de los consentimientos ya firmados.

### Sprint 38 — Módulo de documentos: visualización, vista previa, escaneo y gestión (hecho)
- **Bug de visualización corregido (causa raíz):** el serializer exponía `file` crudo → DRF lo devolvía como URL absoluta con host interno (localhost) → Mixed Content/ERR_CONNECTION_REFUSED; el frontend agravaba con `href={d.file}` y `src={d.file}`. Ahora el serializer devuelve `file_url` RELATIVA y el frontend la resuelve con `fileSrc()` (igual que logos y consentimientos). Los documentos ya almacenados siguen funcionando.
- **Endpoint de archivo autenticado** `patients/<pk>/documents/<id>/file/` (Sprint 38): valida tenant + paciente + permisos antes de entregar el binario, con Content-Type correcto e inline/attachment según `?download=1`. Cierra el acceso no autenticado que existía al servir `/media/` directo.
- **Vista previa en modal** (`lib/DocumentPreview.js`) para PDF, JPG, JPEG, PNG (y otras imágenes): ampliar, reducir, rotar, descargar e imprimir, sin abandonar la página. Carga el archivo autenticado vía blob.
- **Escaneo por cámara** (`lib/DocumentScanner.js`): captura de una o varias páginas con `getUserMedia`, realce de brillo/contraste, y combinación en un único PDF que se guarda en la historia clínica. (TWAIN/WIA no es accesible desde el navegador por seguridad; se documenta como limitación y se ofrece la captura por cámara, que cubre el caso habitual. Recorte de bordes y corrección de perspectiva quedan como mejora futura con OpenCV.js.)
- **Gestión documental:** vista en cuadrícula y en lista, búsqueda por nombre/descripción, filtro por categoría y por fecha, orden por fecha o nombre, y metadatos visibles (tamaño del archivo, fecha, quién lo cargó). El serializer añade `file_name`, `file_size`, `doc_type_display` y `uploaded_by_name`.
- **Seguridad verificada con tests:** aislamiento por clínica (un usuario de otra clínica recibe 404 al pedir el archivo), pertenencia al paciente correcto, autenticación obligatoria en la descarga.

### Sprint 39 — Eliminación de documentos y arranque robusto (hecho)
- **Eliminar documentos** (subidos o escaneados): botón en la vista de cuadrícula (✕ en la esquina de la tarjeta), en la vista de lista y dentro del modal de vista previa, siempre con diálogo de confirmación. Endpoint `DELETE patients/<pk>/documents/<id>/` con **borrado suave** (`is_active=False`): el documento desaparece del listado y su archivo deja de ser accesible (404), pero el registro se conserva para la trazabilidad de la historia clínica. Solo admin y doctor pueden eliminar (recepción recibe 403) y cada clínica solo puede eliminar lo suyo (404 entre tenants). Verificado con tests.
- **Arranque robusto:** `scripts/start-codespace.sh` ahora espera al daemon de Docker (hasta 60 s) e intenta arrancarlo si no responde, en lugar de fallar con "Cannot connect to the Docker daemon" cuando docker-in-docker todavía está iniciando tras un reinicio del Codespace. Si no levanta, muestra la instrucción de rebuild.

### Sprint 40 — Sistema de diseño: temas claro/oscuro y refinamiento visual (hecho)
100% presentación; la lógica de negocio no cambia (la suite sigue en 153 tests).
- **Dos capas de color separadas** en `globals.css`: la capa de MARCA (`--petrol`, `--mint`…) la sigue escribiendo `theme.js` desde el logotipo de cada clínica, y la capa de SUPERFICIE (`--paper`, `--card`, `--ink`, `--line`…) cambia con el modo. Así cada clínica conserva su identidad tanto en claro como en oscuro.
- **Modo claro / oscuro / sistema** con control segmentado de tres estados en la barra lateral (`lib/ThemeSwitch.js`), preferencia persistida, y seguimiento automático del sistema operativo mientras esté en "Sistema". Un script síncrono en el layout raíz fija el tema antes del primer pintado para evitar el parpadeo de tema.
- **Contraste garantizado en ambos modos:** en claro la marca se oscurece hasta contrastar con texto blanco; en oscuro se aclara hasta contrastar con el fondo profundo (`ensureAccessibleOnDark`), y el botón primario invierte su texto a tinta. Verificado ≥ 4.5:1 (WCAG AA) sobre los seis presets y colores extraídos de logotipos reales.
- **Escala tipográfica** (razón 1.2), jerarquía por peso y tracking negativo en titulares, cifras tabulares en datos; **escala de espaciado** de 4; tres niveles de **elevación** con sombras de tinta; radios y estados de interacción (hover, focus visible con doble anillo, active que hunde 1px).
- **Movimiento deliberado:** tres gestos reutilizados en todo el sistema —aparecer (contenido y páginas), emerger (modales) y latir (carga)— con duraciones cortas (120-260 ms) pensadas para uso intensivo, y `prefers-reduced-motion` respetado.
- **Responsive y superficies:** puntos de corte en 900 px y 640 px, tablas con desplazamiento dentro de su tarjeta en móvil, barras de desplazamiento acordes al modo, y hoja de impresión para los documentos clínicos. Superficies fijas (`#fff`) migradas a tokens para que sigan al tema.
- **Nota sobre True Tone:** es una adaptación de hardware del panel; una página web no puede leerla ni controlarla. Lo que sí se hace: declarar `color-scheme` (que integra el interfaz con la gestión de color del sistema) y usar neutros ligeramente cálidos en vez de grises azulados, de modo que bajo la corrección de blancos el interfaz no vire a un tono sucio.

### Sprint 41 — Tema oscuro sobrio, refinamiento de componentes y fix de Documentos (hecho)
- **Bug corregido en Documentos (causa raíz):** `DocumentsTab` desestructuraba `useConfirm()` como objeto (`const { confirm, ConfirmUI }`) cuando el hook devuelve una **tupla** `[confirm, ui]`, dejando ambos valores en `undefined`; además renderizaba `<ConfirmUI />` como componente cuando `ui` es un **elemento JSX**. De ahí el "Element type is invalid… got: undefined". Corregido a `const [confirm, ConfirmUI] = useConfirm()` y `{ConfirmUI}`, igual que el resto del sistema. Verificado además que todos los componentes usados en el módulo estén exportados e importados correctamente.
- **Tema oscuro rediseñado:** el sidebar ya no toma el color de marca (que al aclararse para contrastar se volvía un bloque saturado). Se añadieron tokens propios de navegación (`--nav-bg`, `--nav-ink`, `--nav-line`, `--nav-hover`, `--nav-active-ink`): en claro siguen siendo una franja de marca profunda, y en oscuro una superficie neutra (#0b1113) donde la marca aparece solo como acento del elemento activo.
- **Acentos suaves:** en modo oscuro la saturación de la marca se atenúa (tope 0.52) antes de aclararla, de modo que el matiz —y la identidad de la clínica— se conserva sin estridencia. Verificado ≥ 4.5:1 (WCAG AA) para vino, azul, naranja, petróleo y bosque.
- **Selector de apariencia corregido:** el indicador deslizante quedaba desalineado sobre las etiquetas porque el `gap` de la rejilla rompía el cálculo de porcentajes; ahora se desplaza por `transform` en múltiplos exactos del ancho de columna.
- **Componentes refinados:** iconos alineados y de tamaño fijo dentro de los botones, variante `.btn-danger` coherente, estados `:disabled` en campos, selectores con flecha propia (idéntica en ambos modos y navegadores), cabeceras de tabla fijas al desplazar, y colores fijos del sidebar migrados a tokens.

### Sprint 42 — Selector de tema, contrastes del modo oscuro y reemplazo de logotipo (hecho)
- **Selector de apariencia corregido:** la causa del desalineado era `repeat(3, 1fr)`, que NO produce columnas iguales (`1fr` equivale a `minmax(auto, 1fr)`, así que la columna de "Sistema" crecía con su texto y el indicador dejaba de coincidir); se cambió a `minmax(0, 1fr)`. Además, icono + texto de tres opciones no cabía en los ~180 px útiles del sidebar: ahora el control es de solo iconos, con `title` y `aria-label` por opción y un rótulo "Apariencia" encima.
- **Contrastes del modo oscuro corregidos:** nueva clase `.success-box` (los mensajes de éxito reutilizaban `.error-box` con menta + petróleo profundo en línea, que en oscuro quedaba claro sobre claro e ilegible); token `--mint-ink` para el texto sobre fondos de menta (etiquetas de fila en la tabla CPO-ceo); celdas de totales del crema fijo `#f8d9bf` a los tokens de ámbar; botones de indicadores de salud bucal de `#fff` a `--elev`; y superficies claras fijas restantes en Pagos y Plataforma migradas a tokens. Verificado ≥ 4.5:1 en las nueve combinaciones de texto/fondo del modo oscuro.
- **Reemplazo de logotipo:** `logoSrc()` ahora versiona la URL con `updated_at`, de modo que al reemplazar el logotipo la vista previa, el sidebar y el favicon muestran la imagen nueva en vez de la cacheada por el navegador. En el backend, al reemplazar se elimina el archivo anterior del disco (resuelve además la acumulación de logotipos huérfanos de cada prueba).

### Sprint 43 — Identidad clínica azul y contrastes de Agenda (hecho)
- **Agenda corregida:** las celdas del calendario mensual se pintaban con `#fff` fijo, quedando blancas sobre el fondo oscuro; ahora usan `--elev`. El control segmentado Día/Semana/Mes usaba blanco fijo para las opciones inactivas y texto blanco para la activa: ahora usa `--elev` / `--ink-soft` y `--on-brand`. Sombra del selector migrada al token del sistema.
- **Nuevo token `--on-brand`:** color de texto legible SOBRE la marca (blanco en claro, tinta profunda en oscuro). Reemplaza los `color: "#fff"` escritos a mano en botones, pastillas activas y chips, que en oscuro quedaban blanco sobre un azul claro.
- **Identidad visual del sector salud como tema por defecto:** azul clínico `#14639e` con acento cielo `#bcdcf2`. En claro predominan blancos y grises levemente azulados (`#f4f7fa` lienzo, tarjetas blancas); en oscuro, azules profundos y grises neutros (`#0d141b` lienzo, `#141d26` tarjetas, `#0a1017` navegación), con saturación baja para transmitir limpieza sin cansar en jornadas largas. Sombras con tinta azulada y semánticos (verde/ámbar/rojo) armonizados con la paleta fría.
- **La personalización se mantiene intacta:** el preset "Petróleo" anterior sigue disponible en la lista, junto a Océano, Bosque, Vino, Grafito y Arena, y siguen funcionando los colores manuales y la extracción automática desde el logotipo. Solo cambia cuál es el tema del sistema.
- Contraste verificado en ambos modos: de 3.49:1 (etiquetas tenues, mínimo AA grande 3:1) a 16.32:1, con la marca en 6.35:1 sobre blanco y 4.72:1 en su variante oscura.

### Sprint 44 — Adaptación a móvil y tablet (hecho)
- **Menú lateral como panel deslizante en pantallas estrechas (≤ 860 px):** antes ocupaba media pantalla del teléfono. Ahora se oculta fuera de vista y se abre con el botón de menú de una nueva barra superior (que muestra logotipo y nombre de la clínica); se cierra al tocar el fondo oscurecido, la ✕ o cualquier sección. Con el panel abierto se bloquea el desplazamiento del fondo. En móvil el menú siempre muestra las etiquetas —contraer a solo iconos es una función de escritorio— y el área principal ocupa todo el ancho.
- **Botón de contraer rediseñado:** los glifos de texto « » se veían descentrados y de tamaño irregular. Ahora es un icono SVG de doble punta de flecha que gira según el estado, dentro de un botón circular de 30 px centrado en su fila, con el mismo trazo que el resto de la iconografía.
- **Contenido adaptable:** las filas de pestañas (ficha del paciente y configuración) se desplazan en horizontal en vez de partirse en varias líneas; objetivos táctiles más cómodos en botones y campos (≈44 px de alto); titulares y espaciado reducidos en pantallas pequeñas.

### Sprint 45 — Cobros en ficha, avisos del día, navegación y color por profesional (hecho)
- **Cobros desde la ficha del paciente:** nueva pestaña "Cobros" (solo admin y recepción) con el historial y el registro directo sin salir de la ficha. Endpoint `patients/<pk>/payments/`; el pago queda sin cuota asociada, que el modelo ya contemplaba (`installment` es opcional), así que no hizo falta migración. Los abonos a un plan de financiamiento siguen en el módulo Pagos, que es donde vive esa lógica.
- **Botón "Regresar"** (`lib/BackButton.js`) en la ficha del paciente, Pagos, Reportes, Inventario y Configuración. Usa el historial del navegador y, si la persona llegó por enlace directo, cae a una ruta segura en vez de dejarla fuera del panel.
- **Icono de contraer sustituido:** la doble punta de flecha se confundía con "regresar". Ahora es un icono de panel lateral (marco con su columna izquierda resaltada), que comunica plegar/desplegar en vez de una dirección.
- **Recordatorios de cumpleaños:** endpoint `patients/birthdays/?days=7` que compara mes y día (funciona en cualquier año) y tarjeta en el panel de inicio con los cumpleaños de hoy y de la semana, con la edad que cumple cada paciente y enlace a su ficha.
- **Aviso de llegada al profesional:** endpoint `appointments/waiting/` y tarjeta en el panel. El odontólogo ve sus pacientes en sala; recepción y administración, los de toda la clínica, con los minutos de espera (en rojo a partir de 15). No requirió un modelo de notificaciones: la señal ya estaba en los datos (hay check-in y la atención no ha comenzado), de modo que el aviso siempre es coherente con el estado real de la agenda y no puede quedar "pegado". Se refresca cada minuto. El aviso por WhatsApp que ya existía sigue funcionando en paralelo.
- **Color identificativo por profesional en la agenda:** franja lateral y punto de color en cada cita, más una leyenda cuando hay varios profesionales. Usa el campo `calendar_color` que el modelo `Doctor` ya tenía; si algún profesional no lo tiene configurado, se deriva un color estable de su nombre para que nunca queden dos agendas indistinguibles.

### Sprint 46 — Múltiples modelos de odontograma (patrón Strategy) (hecho)
100% presentación: la estructura clínica y los datos almacenados no cambian (la suite sigue en 156 tests).
- **Capa de estrategia** en `lib/odontogram/`: `contract.js` documenta el contrato que todo modelo debe cumplir y centraliza la disposición FDI; `registry.js` es el punto único de extensión (añadir un cuarto modelo es crear un componente y registrarlo, sin tocar la lógica clínica).
- **Tres modelos intercambiables** con selector en la pestaña Odontograma, y la preferencia recordada por persona (`localStorage`, no viaja al servidor porque es una preferencia de vista, no un dato clínico):
  - **Clásico** (predeterminado): el esquema MSP por superficies que ya existía, sin cambios.
  - **Anatómico**: silueta de la corona según la familia de la pieza (incisivo, canino, premolar, molar, derivada del último dígito FDI) más una rueda de cinco superficies; la arcada inferior se dibuja en espejo.
  - **Compacto**: cuadrícula por cuadrantes en HTML, con cinco franjas de color por pieza y selección de superficie con botones grandes; pensado para pantallas pequeñas y revisión rápida.
- **Una sola fuente de datos, garantizada por diseño:** los tres modelos reciben exactamente las mismas props y emiten las mismas intenciones (`onSurfaceClick`, `onRMClick`); ninguno tiene estado propio, efectos ni llamadas a la API. El registro ocurre una única vez en el contenedor `OdontogramTab`, de modo que cambiar de modelo no puede alterar ni duplicar información, y el historial por pieza, los índices CPO-ceo, los diagnósticos y las exportaciones (PDF, formulario oficial MSP) se generan siempre desde lo almacenado, con independencia del modelo usado para registrar.
- **Nota de alcance:** la edición de recesión y movilidad sigue disponible solo en el modelo Clásico, que es donde vive esa fila; los otros dos se centran en superficies. Cambiar de modelo para editarlas no afecta a los datos.

### Sprint 47 — Set de ilustraciones dentales anatómicas (hecho)
100% presentación; la lógica y los datos no cambian (la suite sigue en 156 tests).
- **Ilustraciones vectoriales dibujadas a medida** (`lib/odontogram/ToothArt.js`), no imágenes de mapa de bits: escalan sin pérdida en pantallas retina de tablet, heredan los tokens del tema (funcionan en claro y oscuro sin mantener dos juegos de recursos), pesan bytes en vez de kilobytes y no dependen de recursos de terceros ni de sus licencias. Además, al ser vectores cada superficie sigue siendo una región clicable con su color clínico encima, cosa que un dibujo plano no permitiría.
- **Morfología según anatomía real:** la familia dental se deduce del último dígito FDI (incisivo, canino, premolar, molar; en las piezas temporales, los dígitos 4 y 5 son molares) y el número de raíces del cuadrante — tres en molares superiores, dos en inferiores y en el primer premolar superior, una en el resto. La corona cambia de perfil, número de cúspides y surcos por familia; las piezas temporales son más estrechas y de raíz más corta. La arcada inferior se dibuja reflejada.
- **Nuevos tokens de color dental** (`--tooth-enamel-hi`, `--tooth-enamel`, `--tooth-dentin`, `--tooth-root`, `--tooth-stroke`, `--tooth-groove`) con degradado de esmalte a dentina. En modo oscuro la pieza no se invierte a negro: sigue leyéndose como diente claro, solo atenuado, para no perder la referencia anatómica ni deslumbrar.
- **Modelo anatómico recompuesto en HTML** (una celda por pieza en vez de un único SVG con coordenadas absolutas): cada diente es un objetivo táctil independiente y la rejilla se reordena sola en tablet. El modelo compacto incorpora miniaturas de 26 px que permiten identificar la familia dental de un vistazo.
- La garantía del Sprint 46 se mantiene verificada: los tres modelos y el set de ilustraciones siguen sin escrituras, sin estado y sin efectos.

### Sprint 48 — Odontograma 3D (hecho)
100% presentación; sin tablas ni registros nuevos (la suite sigue en 156 tests).
- **Nueva pestaña "Odontograma 3D"** en la ficha del paciente. No es un módulo aparte: monta el MISMO contenedor `OdontogramTab` con la vista fijada en 3D, de modo que comparte al cien por cien la carga de datos, el registro y el historial. Es también la cuarta estrategia del registro (`registry.js`), así que aparece igualmente en el selector de modelos.
- **Tipodonto interactivo** (`lib/odontogram/Odontogram3D.js`) con rotación (arrastrar), zoom (rueda), desplazamiento (Mayús + arrastrar) y selección de piezas por raycasting. Órbita implementada a mano para no depender de complementos fuera del paquete.
- **Geometría procedural:** las piezas se generan desde el número FDI (dimensiones por familia dental, estrechamiento hacia el cuello, distribución sobre una elipse que reproduce la forma de la arcada) en vez de cargar un modelo descargado. Esto evita depender de recursos de terceros y de sus licencias, y —lo decisivo— hace que cada diente sea un objeto independiente sobre el que se puede hacer raycasting; una malla única importada no lo permitiría sin trabajo de segmentación.
- **Representación de tratamientos:** color por estado clínico, y material metálico y pulido para coronas, implantes y prótesis, de modo que los materiales restauradores se distinguen de la pieza natural.
- **Filtros** para resaltar caries, obturaciones, coronas, endodoncias, implantes, prótesis, extracciones, sellantes, fracturas o cualquier pieza con registro. Lo que no coincide se atenúa en vez de ocultarse, para no perder la referencia anatómica de la boca completa.
- **Panel lateral** al seleccionar una pieza: estado actual por superficie e historial clínico completo, alimentado por los datos que el contenedor ya cargaba.
- **Animaciones suaves:** la pieza seleccionada se separa de la arcada y crece; los cambios de opacidad, escala y posición se interpolan por fotograma.
- **Captura de imagen** de la vista actual en PNG para informes y explicación al paciente (`preserveDrawingBuffer` en el renderizador).
- **Rendimiento:** Three.js se importa de forma diferida, así que su peso no entra en el paquete inicial y la escena solo se construye al abrir la pestaña; geometría de bajo polígono, sin sombras, con liberación de recursos al desmontar.
- **Sincronización garantizada por diseño:** el modelo 3D no tiene base de datos propia ni una sola llamada a la API (verificado). Un efecto reacciona a los datos clínicos y actualiza colores, materiales y filtros, de modo que un registro hecho en cualquier otro modelo se refleja aquí de inmediato, y viceversa.

### Sprint 49 — Realismo del odontograma 3D (hecho)
100% presentación; sin cambios de datos ni de lógica (la suite sigue en 156 tests).
- **Geometría anatómica generada por lofting** (`lib/odontogram/toothGeometry.js`), en sustitución de las cajas: se apilan secciones transversales a lo largo del eje del diente y se cosen con normales suavizadas. La forma se controla con dos funciones —radio(θ,t) y altura(θ,t)— que producen cuatro cúspides en un molar, dos en un premolar, una en un canino y un borde en lámina en un incisivo; el perfil vertical reproduce el ecuador en el tercio medio de la corona, la constricción cervical y raíces que afinan hasta el ápice. El número de raíces sigue la anatomía (tres en molares superiores, dos en inferiores y en el primer premolar superior, una en el resto) y las piezas temporales son más bulbosas y de raíz corta. Unos 1.400 triángulos por corona, con normales suavizadas para que no se vean facetas.
- **Materiales PBR:** esmalte con `MeshPhysicalMaterial`, capa de barniz (`clearcoat`), transmisión e índice de refracción 1.63 con atenuación cálida, que es lo que evita el aspecto de plástico blanco; encía translúcida con su propio material físico.
- **Entorno para reflejos:** mapa generado proceduralmente con `RoomEnvironment` (incluido en el paquete de three, no se descarga nada) y preconvolucionado con `PMREMGenerator`. Sin entorno, un material físico no tiene nada que reflejar.
- **Iluminación de tres puntos** (principal cálida cenital con sombra, relleno frío lateral y contraluz posterior) más hemisférica de ambiente, con tono ACES Filmic para que los blancos del esmalte no se quemen.
- **Sombras suaves** (`PCFSoftShadowMap`) sobre un plano receptor invisible que da asiento a las arcadas.
- **Selección por contorno luminoso:** malla ampliada dibujada por su cara interna, que aparece y desaparece interpolada, en vez de recolorear la pieza.
- **Patologías como tinte sobre el esmalte:** el color clínico se mezcla al 62 % con el marfil natural y añade un halo tenue, de modo que el hallazgo es inequívoco pero el diente conserva translucidez y reflejos. Los materiales restauradores se distinguen además por acabado: implante metálico pulido, corona muy pulida, prótesis cerámica mate.
- **Cámara:** giro vertical amplio (360° útiles), zoom de 4.5 a 30 unidades y desplazamiento libre; todas las transiciones interpoladas por fotograma.
- Se mantienen la liberación de recursos al desmontar (incluidos contornos y mapa de entorno) y la garantía de que el modelo 3D no realiza ninguna llamada a la API.

### Sprint 52 — Ficha periodontal completa como odontograma compacto (hecho)
Sustituye la implementación del Sprint 51. Con la autorización explícita para modificar el modelo de datos, se implementó la capa que faltaba: las capturas del proyecto de referencia no muestran un odontograma sino un **periodontograma** (Available, Implant, Mobility, Furcation, Bleeding on Probing, Plaque, Gum Width, Gingival Margin, Probing Depth, con seis sitios por diente e índices al pie).
- **Modelos nuevos** (`clinical/0012`): `PeriodontalExam` (sesión de exploración por paciente y fecha, permite comparar evolución entre sesiones) y `PeriodontalTooth` (presencia, implante, movilidad, furcación vestibular y lingual, ancho de encía, y cuatro series de **seis sitios**: sondaje, margen gingival, sangrado y placa). El orden de sitios sigue la convención periodontal: 0-2 vestibular mesial/central/distal, 3-5 palatino/lingual. Las series se guardan en JSON en vez de veinticuatro columnas sueltas; el serializador valida longitud y rango (-10 a 20 mm, margen negativo admitido por recesión). El **nivel de inserción no se almacena**: es derivado (sondaje + margen).
- **Endpoints:** `patients/<pk>/periodontal-exams/` (al crear una exploración se siembran las 32 piezas permanentes en orden clínico, de modo que la matriz llega completa) y `periodontal-teeth/<id>/` con PATCH parcial. **Índices agregados** calculados siempre desde lo almacenado: sondaje medio, nivel de inserción medio, % de placa y % de sangrado sobre los sitios de piezas presentes (las ausentes quedan fuera del cálculo).
- **Matriz clínica** (`lib/periodontal/PeriodontalMatrix.js`) con todas las filas de la ficha original más las cinco filas de **estados por superficie** del sistema; etiquetas de fila fijas, línea media, notación con punto, ilustración por pieza, navegación por cuadrante, cursor de teclado, zoom, desplazamiento automático a la pieza activa, panel contextual y realce por escala (1.35×) heredado de `.circle-nerve-clicked`.
- **Celdas desacopladas y reutilizables** (`lib/periodontal/cells.js`): interruptor de presencia, casilla de implante, selector de grado, marcador de furcación por grados, fila de banderas de sitio y fila numérica de sitio, todas con roles ARIA. Los valores de sondaje mayores de 4 mm se destacan automáticamente.
- **Guardado diferido y optimista:** los cambios se acumulan por pieza y se envían 450 ms después de la última edición (escribir seis sondajes produce una petición, no seis), con actualización inmediata en pantalla y recarga posterior para traer derivados e índices.
- **Nota de arquitectura documentada en el propio archivo:** este modelo es un híbrido deliberado y el único de los cuatro que no es renderizador puro. Los estados por superficie siguen llegando por props desde `OdontogramTab` —así que registrar aquí se refleja al instante en el clásico y en el 3D—, mientras las mediciones periodontales, que ningún otro modelo posee, las gestiona este componente contra sus propios endpoints. Verificado que los otros tres modelos siguen sin escrituras. El formulario MSP 033 continúa usando el odontograma clásico, como se acordó.
- La separación en tablas propias deja la arquitectura preparada para ortodoncia e implantología como capas adicionales sobre las mismas piezas.

### Sprint 53 — Realismo visual del odontograma 3D (hecho)
100% presentación: no cambian los datos, ni la lógica clínica, ni la
interacción (rotación, zoom, selección y gestos táctiles siguen igual).
Se corrigieron además tres defectos de malla que deformaban el modelo.

- **Tres errores de fondo corregidos:**
  1. *Piezas giradas 90°.* La geometría define vestibular en el eje X local,
     pero la colocación usaba `lookAt`, que alinea el eje Z. Los incisivos se
     veían como agujas y las coronas se solapaban entre sí. Ahora la
     orientación es explícita (X mesio-distal siguiendo la tangente de la
     arcada, Z vestibular hacia fuera).
  2. *Caras de la raíz invertidas.* Corona y raíz se cosían con el mismo
     orden de vértices pese a recorrerse en sentidos opuestos, así que las
     caras de la raíz miraban hacia dentro, el descarte de caras traseras se
     las comía y se abría un hueco negro en el cuello de cada pieza.
  3. *Normales corruptas.* El arreglo de la costura UV recorría los vértices
     a saltos fijos, pero entre anillo y anillo hay vértices sueltos (fosa
     central, ápices, tapas de la furca); a partir del primero, promediaba
     normales de vértices sin relación.
- **Anatomía dental real** (`toothGeometry.js`): sección transversal por
  familia mediante superelipse (el molar tiende al cuadrado redondeado, el
  incisivo a una lámina), achatamiento vestíbulo-lingual progresivo que
  convierte el borde incisal en un cincel, y **cara oclusal resuelta como
  campo de altura** —cúspides con su número y posición por pieza, fosa
  central, surcos de desarrollo en cruz, rebordes marginales y cresta
  oblicua del molar superior— en vez de una tapa plana. Proporciones
  ajustadas a las medias reales de cada pieza.
- **Encía nueva** (`gingivaGeometry.js`): sustituye los dos toros achatados,
  que al ser circunferencias sobre arcadas elípticas atravesaban unas piezas
  y dejaban otras al aire. Se genera sobre la MISMA curva que coloca los
  dientes, con margen festoneado (cénit sobre cada pieza y papila en cada
  tronera), eminencias radiculares, encía adherida, unión mucogingival y
  fondo de vestíbulo. El borde visible es la intersección con la pieza, de
  modo que sigue su contorno y no puede dejar huecos.
- **Reparto por longitud de arco** (`archCurve.js`): las piezas se distribuyen
  según su ancho mesio-distal real. En una elipse, pasos angulares iguales dan
  separaciones desiguales, que es lo que amontonaba los molares.
- **Texturas procedurales** (`dentalTextures.js`), dibujadas en canvas y
  compartidas: rugosidad y microrrelieve del esmalte (perikimatíes en la
  corona, cemento mate en la raíz) y punteado de cáscara de naranja de la
  encía adherida. Un material de rugosidad constante da un brillo uniforme,
  que es el rasgo que delata el plástico.
- **Color por vértice** de esmalte translúcido a dentina cervical y cemento,
  dejando el color del material libre para el estado clínico.
- **Luz y sombra:** cuatro focos (principal cálida con sombra, relleno frío,
  contraluz y rebote inferior), encuadre del mapa de sombras ajustado a las
  arcadas y brillo especular más amplio y suave.
- **Rendimiento:** malla **indexada** (un tercio de la memoria de vértices) y
  **compartida** entre piezas equivalentes — de 52 mallas únicas a diez—,
  la encía no entra en el paso de sombras y desaparecen las 52 mallas de
  contorno: el realce de selección pasa a ser una emisión sobre el propio
  material. Medido en el rasterizador por software del entorno de pruebas,
  el coste queda ~12 % por encima del anterior con mucha más superficie en
  pantalla; en GPU real la diferencia es menor.


### Sprint 54 — Anatomía por pieza y acabado del odontograma 3D (hecho)
Segunda vuelta sobre el modelo 3D. Sigue siendo 100% presentación: no
cambian los datos, la lógica clínica ni la interacción.

- **Bug corregido en el caché de geometría:** la clave no distinguía la
  cara oclusal, así que el primer molar inferior (cinco cúspides, patrón
  Y5) y el segundo (cuatro) compartían malla y ganaba el que se
  construyera primero. Ahora la variante oclusal entra en la clave.
- **Anatomía por pieza:** proporciones propias de cada diente dentro de su
  familia (el lateral superior frente al central, los incisivos inferiores
  como piezas más estrechas de la boca, el primer molar mayor que el
  cordal), aplicadas como escala del objeto para no romper la
  reutilización de mallas.
- **Postura real en la arcada** (`toothPose`): torque vestíbulo-lingual e
  inclinación mesio-distal por familia, siguiendo el orden de la
  prescripción ortodóncica habitual, y curva de Spee que acerca los
  sectores posteriores al plano oclusal. Antes todas las piezas quedaban
  verticales y paralelas.
- **Contactos interproximales:** las piezas se reparten prácticamente sin
  holgura y las secciones llevan convexidad proximal, de modo que las
  coronas se tocan en su punto de contacto en vez de dejar rendijas.
- **Oclusión ambiental horneada en el color de vértice**, gratis en tiempo
  de ejecución: las fosas y los surcos de desarrollo se oscurecen (las
  fisuras se leen como surcos y no como un dibujo), las caras proximales
  se ensombrecen hacia el cuello (sin ello las coronas contiguas se
  funden en una masa clara continua) y la encía dibuja la sombra del
  surco donde se encuentra con cada diente.
- **Encía ligada al cuello real de cada pieza:** la altura del margen se
  interpola entre piezas vecinas a partir de su cuello, que la curva de
  Spee desplaza. Con un margen a altura constante el tejido se despegaba
  en unas piezas y montaba sobre la corona en otras.
- **Transición de color continua** esmalte → dentina cervical → cemento
  con una sola función axial; antes había dos funciones distintas y el
  salto entre ambas dibujaba un anillo en el cuello.
- **Malla más suave:** anillos agrupados en los extremos (donde está la
  curvatura) en vez de repartidos por igual, lo que da la misma suavidad
  aparente con menos triángulos y permitió subir el detalle oclusal.
- **Cara oclusal más detallada:** cúspides con número y posición propios
  de cada pieza —incluida la quinta del primer molar inferior—, rebordes
  marginales, cresta oblicua del molar superior, cíngulo y fosa lingual
  en el sector anterior, y ángulos incisales redondeados en el lateral.
- **Iluminación contrastada:** el reparto de intensidades entre los cuatro
  focos era demasiado plano; repartir la luz por igual ilumina todas las
  caras y anula el volumen.


### Sprint 55 — Oclusión ambiental en pantalla y mapas de normales (hecho)

**Nota de alcance, importante.** El objetivo de este sprint era sustituir
la geometría procedural por mallas dentales escaneadas de alta calidad.
No fue posible en este entorno: ninguna de las fuentes con licencia
utilizable resultó accesible (NIH 3D devuelve 404 en su API, BodyParts3D
y Smithsonian responden 403, la API de GitHub está limitada a los
repositorios de la sesión y los paquetes dentales de npm resultaron ser
también procedurales, sin mallas). Además, las fuentes anatómicas
realistas que existen suelen estar bajo CC BY-SA —licencia vírica— lo que
para un producto clínico comercial es una decisión que corresponde
tomar al responsable del proyecto, no darla por hecha.

Ante eso, este sprint ataca la otra mitad del problema: **el motor de
render**, que es donde se juega buena parte del acabado profesional.

- **Oclusión ambiental en espacio de pantalla (GTAO):** cadena de
  post-proceso con `EffectComposer`. Los rincones donde dos superficies
  se acercan —tronera interdental, surco gingival, fondo de fisura,
  encuentro de corona y encía— reciben menos luz del entorno; ninguna luz
  direccional reproduce eso, hay que calcularlo desde la profundidad y
  las normales de la escena. Es lo que más acerca el resultado al aspecto
  de un render clínico.
- **Repliegue seguro:** si el paso no está disponible o falla al
  compilar, se dibuja directo como antes. La escena nunca depende del
  post-proceso.
- **Salvaguarda de rendimiento:** se mide el coste real durante los
  primeros 40 fotogramas y, si el equipo no sostiene 35 fps, el
  post-proceso se desactiva solo. Antes fluidez que oclusión.
- **Mapas de normales** en sustitución de los de relieve: la pendiente va
  precalculada en la textura en vez de derivarse por píxel, así que el
  microrrelieve se ve firme y cuesta menos. Se generan por Sobel desde el
  mismo campo de altura, de modo que relieve y normales no discrepan.
- La captura de imagen para informes pasa por la MISMA cadena que la
  pantalla; si no, saldría sin oclusión y no coincidiría con lo que ve el
  profesional.

**Lo que sigue pendiente para el salto de realismo:** mallas por pieza de
origen escaneado. Requiere decidir la licencia (CC BY-SA obliga a
compartir en las mismas condiciones), un pipeline de conversión a glTF
con compresión, y normalizar orientación y escala de cada pieza al marco
local que ya usa el sistema (`+X` mesio-distal, `+Z` vestibular, cuello
en el origen). La capa de colocación, la encía, el raycasting y la
sincronización clínica están preparadas para recibirlas sin cambios.


### Sprint 56 — Proveedor de mallas y variación anatómica (hecho)
El motor de render deja de saber CÓMO se fabrica un diente.

- **Interfaz `MeshProvider`** (`lib/odontogram/meshProvider.js`): el motor
  pide una pieza por su número FDI y recibe siempre lo mismo —geometría
  en el marco local canónico, escala y medidas—. Hay dos proveedores:
  - *procedural*, el generador actual, siempre disponible;
  - *gltf*, que carga mallas `.glb`/`.gltf` desde `public/models/teeth/`.
- **Listo para mallas profesionales sin tocar código:** basta con dejar
  los ficheros y un `manifest.json` en esa carpeta. El manifiesto puede
  corregir orientación, escala y origen de cada pieza, de modo que no hay
  que reexportar los modelos para adaptarlos al marco del sistema. Si una
  pieza falta, la cubre la procedural: un juego incompleto nunca deja
  huecos en la arcada. Si no hay manifiesto, no se emite ni un error en
  consola. Documentado en `public/models/teeth/README.md`.
- **Independencia real:** las medidas (`mdWidth`, `blDepth`, `crownH`,
  `rootH`) las publica el proveedor, así que el reparto por longitud de
  arco, el margen gingival que sigue el cuello, el raycasting, la
  selección, el historial y la sincronización clínica funcionan igual
  venga la malla de donde venga.
- **Variación anatómica por pieza:** desviaciones pequeñas de tamaño y
  aplomo derivadas de forma DETERMINISTA del número FDI. Una arcada de
  piezas idénticas se lee de inmediato como generada por ordenador; al
  ser determinista, la misma pieza tiene siempre la misma variación y el
  modelo no cambia entre visitas ni entre exportaciones del informe.
- **Adaptación al tema claro/oscuro:** el lienzo es transparente y se ve
  sobre el fondo de la aplicación. Se mide la luminancia REAL del fondo
  —no el nombre del tema— para que funcione también con los colores de
  marca de cada clínica, y se ajustan exposición, luces y entorno.
- **Cámara inicial** más cercana y con un ángulo menos cenital.
- **Limpieza:** eliminados los generadores de mapas de relieve, sin uso
  desde que el microrrelieve va por mapas de normales.


### Sprint 57 — Lóbulos de desarrollo y anatomía radicular (hecho)
Salto anatómico del generador procedural. Sin tocar la lógica clínica, la
sincronización, el raycasting ni la arquitectura `MeshProvider`.

- **Lóbulos de desarrollo.** Era el límite de fondo del generador: todas
  las familias usaban la misma sección transversal (una superelipse
  escalada), así que solo se diferenciaban en proporciones. Una corona no
  crece como un cilindro, se forma a partir de lóbulos que se fusionan, y
  los surcos que quedan entre ellos son lo que da a cada familia su
  silueta. Ahora se modelan explícitamente:
  - incisivo: tres lóbulos vestibulares —de ahí los mamelones del borde y
    las dos depresiones verticales de la cara— más cíngulo;
  - canino: lóbulo medio dominante, que forma la cresta vestibular;
  - premolar: un lóbulo vestibular marcado y otro palatino menor;
  - molar: dos vestibulares y dos palatinos, uno por cúspide.
  Los lóbulos se difuminan hacia el cuello, donde la corona es lisa, y se
  marcan hacia el tercio oclusal, como en la formación real.
- **Cresta cervical** (cíngulo en el sector anterior, cresta vestibular en
  el posterior): el rodete que rodea la corona junto al cuello, que actúa
  al revés que los lóbulos.
- **Anatomía radicular:** concavidades longitudinales en las caras mesial
  y distal —muy marcadas en el primer premolar superior y en las raíces
  de los molares, y lo que distingue una raíz de un cono liso—, y
  curvatura distal que se acelera hacia el ápice en vez de crecer de
  forma lineal, con valor propio por familia.
- **Bug corregido en el caché:** la variante oclusal del incisivo no
  entraba en la clave, así que el central y el lateral —que redondean sus
  ángulos incisales de forma distinta— compartían malla. Es el mismo
  fallo que ya se corrigió para los molares inferiores.
- **Oclusión ambiental horneada, moderada:** llevada al extremo apagaba
  toda la mesa oclusal —que está llena de valles— y la cara masticatoria
  se leía como un agujero negro en vez de como un relieve.


### Sprint 58 — Asimetría mesio-distal y encía por zonas (hecho)
Refinamiento incremental sobre la arquitectura de lóbulos del Sprint 57.
Sin tocar `meshProvider.js`, el odontograma clásico, el compacto,
`contract.js`, `registry.js` ni `ClinicalTabs.js` (diffs vacíos).

**Encía — la prioridad de este sprint.**
- **Papila propia de cada tramo:** alta y afilada entre incisivos, baja y
  ancha entre molares, donde el espacio interdental es un nicho aplanado
  y no un pico. Antes era un valor único para toda la arcada, y eso hacía
  que el tejido se leyera como una pieza extruida.
- **Grosor por zona:** la encía posterior es sensiblemente más gruesa que
  la del frente, y el margen se sitúa más apical en los sectores
  posteriores.
- **Depresiones interradiculares:** el hueso alveolar se hunde entre raíz
  y raíz. Sin ellas, el conjunto de eminencias radiculares se fundía en
  una superficie continua y la encía volvía a leerse como un bloque; son
  las que dibujan el relieve característico de la tabla vestibular.
- **Altura de margen individual por pieza**, con la misma semilla
  determinista del resto: un festón regular delata el trazado automático
  tanto como una arcada de piezas idénticas.

**Coronas — asimetría mesio-distal.**
- **Ángulo mesioincisal casi recto y distoincisal redondeado** en los
  incisivos, con el cíngulo desplazado a distal. Es el rasgo que permite
  identificar de un vistazo si un incisivo es del lado derecho o del
  izquierdo; sin él, las dos hemiarcadas eran una imagen especular
  perfecta.
- **Canino:** punta cuspídea desplazada a distal, de modo que la
  vertiente mesial queda corta y empinada y la distal larga y tendida, y
  rebordes mesial y distal diferenciados.
- **Primer y segundo premolar con cara oclusal distinta:** en el primero
  domina la cúspide vestibular y el surco central es largo y recto; en el
  segundo las cúspides se equilibran y el surco es más corto y sinuoso.
  Se añadieron las crestas triangulares que bajan de cada cúspide.
- **El lado entra en la clave del caché de geometría:** la pieza derecha
  y la izquierda del mismo número son mallas distintas. Pasa de unas doce
  mallas únicas a unas veinticuatro, cifra irrelevante frente a las 52
  piezas de la boca.


### Sprint 59 — Anatomía radicular, premolares y una incidencia descartada (parcial)

- **Bug corregido en el caché:** el primer y el segundo premolar
  INFERIORES compartían malla pese a tener cara oclusal distinta (los dos
  tienen una sola raíz, así que la clave no los separaba; en los
  superiores se separaban por casualidad porque el primero tiene dos).
  Ganaba el que se construyera primero. Es el mismo fallo que ya apareció
  en molares inferiores e incisivos: ahora la clave incluye el ordinal.
- **Segundo premolar diferenciado:** su surco central se interrumpe en el
  centro y deja dos fositas —mesial y distal— en vez del canal continuo
  del primero, que es lo que los distingue en la vista oclusal. Se
  añadieron además las crestas triangulares que bajan de cada cúspide.
- **Raíces:** torsión progresiva de la sección al descender (rompe el
  aspecto de extrusión recta), aplanamiento mesio-distal creciente hacia
  el ápice, y divergencia real entre raíces —en el molar inferior la
  mesial es más ancha, más larga y se curva más que la distal; en el
  superior la palatina es la mayor—. Antes eran copias simétricas.
- **Cúspides funcionales frente a no funcionales:** en el maxilar las
  palatinas soportan la oclusión y son más altas y romas; en la mandíbula
  lo son las vestibulares.

**Incidencia descartada — caras oclusales oscuras.** No era un defecto del
modelo: el banco de pruebas con el que se revisaba la anatomía no montaba
el mapa de entorno que la escena real sí usa, de modo que las caras
orientadas hacia arriba no tenían nada que reflejar. Añadido el entorno al
banco, el oscurecimiento desaparece. La oclusión ambiental horneada y las
normales están correctas.

**Pendiente — relieve molar.** Se intentó ampliarlo con crestas
triangulares, surco vestibular, fositas accesorias y fisuras secundarias.
El conjunto resta legibilidad en vez de sumarla: las crestas rellenan los
valles entre cúspides y la mesa oclusal queda más plana que la de
partida. Se ha vuelto al relieve anterior, que sí se lee, y queda anotado
en el propio archivo. Hay que rehacerlo midiendo el efecto de cada
término por separado, no sumándolos todos a la vez.


### Sprint 60 — Motor global de estilos de documentos · base (hecho)
Primer sprint de una línea nueva, independiente del odontograma. Objetivo:
que ningún documento lleve colores, tipografías ni márgenes escritos a
mano, y que la apariencia se configure una sola vez por clínica.

- **Modelo `DocumentAppearance`** (migración `configuration/0008`), uno por
  clínica, con nueve grupos de ajustes: encabezado, pie, tipografía,
  paleta, tablas, página, logotipo, firma y marca de agua. Se guardan
  **agrupados en JSON, no en sesenta columnas**: así la tabla no crece con
  cada preferencia y —lo que de verdad importa— un documento futuro puede
  añadir sus propios ajustes sin migración, que es el requisito de que el
  sistema absorba documentos nuevos automáticamente.
- **Compatibilidad hacia atrás por diseño:** `resolved()` rellena con los
  valores por defecto las claves ausentes, de modo que un registro
  guardado antes de que existiera un ajuste nuevo sigue siendo válido y el
  ajuste aparece con su valor por defecto, sin migración de datos.
- **Módulo central `apps/common/document_style.py`:** punto ÚNICO por el
  que un generador obtiene la apariencia. Resuelve tamaño de hoja,
  orientación, márgenes, tipografía, paleta y estilo de tabla, y dibuja
  encabezado, pie y marca de agua. El color primario vacío **hereda la
  marca de la clínica**, de modo que la identidad visual se define en un
  solo sitio.
- **Endpoint `config/document-appearance/`** (GET para todo el personal
  —los generadores y la vista previa lo necesitan—, PATCH y DELETE solo
  admin). El PATCH **fusiona** en vez de sustituir: el panel puede enviar
  solo el grupo tocado sin borrar el resto.
- **Primer generador conectado:** la solicitud de examen complementario ya
  no dibuja su propio encabezado ni usa colores propios; los pide al
  motor. Sirve de patrón para los demás.
- **Excepción documentada:** el formulario MSP HCU-033/2021 NO usa este
  motor. Es un formato oficial del Ministerio con diseño legalmente
  fijado; personalizarlo lo invalidaría.
- **Tests:** 7 nuevos (168 en total), incluyendo el aislamiento entre
  clínicas, la fusión parcial y una prueba de punta a punta que cambia la
  orientación de la hoja y comprueba que el PDF emitido cambia.

**Pendiente de esta línea:** conectar el resto de generadores
(consentimientos, recetas, historia clínica, presupuestos, reportes) y la
pantalla Configuración → Apariencia de documentos con vista previa.


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
