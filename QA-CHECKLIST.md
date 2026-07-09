# Checklist de QA manual — Panel web

Recorrido sistemático de la UI. Marcar cada ítem al verificarlo.
La suite automática (91 tests, incluyendo el E2E de flujo completo)
cubre la API; este checklist cubre lo que solo se ve en el navegador.

## Autenticación
- [ ] Login con credenciales correctas entra al panel.
- [ ] Login con contraseña incorrecta muestra error claro (no crash).
- [ ] Cerrar sesión vuelve al login y no permite volver con "atrás".
- [ ] Tras 30+ min de uso continuo la sesión se renueva sola (refresh token).

## Roles (crear un usuario por rol en el admin de Django y entrar con cada uno)
- [ ] **Recepción:** ve Inicio, Pacientes, Agenda, Pagos. NO ve Inventario/Reportes/Configuración.
- [ ] **Doctor:** ve Inicio, Pacientes, Agenda. NO ve Pagos.
- [ ] **Auxiliar:** ve Inicio, Pacientes, Inventario. NO ve Agenda/Pagos.
- [ ] **Admin:** ve todo.

## Pacientes
- [ ] Registrar paciente con todos los campos y con solo los obligatorios.
- [ ] Cédula duplicada muestra error claro.
- [ ] Búsqueda por nombre, apellido y cédula.
- [ ] Clic en la fila abre la ficha.

## Ficha / Odontograma
- [ ] Registrar estado con notas → confirmación con el modal propio → pieza se pinta.
- [ ] Historial de la pieza muestra todos los registros (no sobrescribe).
- [ ] Eliminar un registro (modal rojo) → la pieza se repinta con el anterior.
- [ ] Evolución: crear, editar (texto anterior queda en auditoría — verificar en admin Django), eliminar.
- [ ] "Registrado por" muestra el nombre correcto.

## Agenda
- [ ] Crear cita buscando paciente por nombre y por cédula.
- [ ] Solapamiento de horario para el mismo doctor → error claro.
- [ ] Cita en el pasado → rechazada.
- [ ] Ciclo completo: Pendiente → Confirmar → Llegó → Finalizar.
- [ ] Vista Semana muestra la columna de fecha; navegación ←/Hoy/→.
- [ ] Filtro por doctor.
- [ ] Paciente moroso → aviso ámbar → "Agendar con excepción" funciona.

## Pagos
- [ ] Presupuesto: agregar ítems (precio se pre-carga del catálogo), total correcto.
- [ ] Aprobar → generar plan (verificar reparto de centavos con $100 en 3 cuotas).
- [ ] Cobro parcial: cuota queda Pendiente con saldo correcto.
- [ ] Cobro del saldo: cuota pasa a Pagada.
- [ ] Tarjetas de estado de cuenta se actualizan tras cada cobro.
- [ ] Tarjeta "Cuotas vencidas" en rojo cuando hay morosidad.

## Inventario
- [ ] Producto con stock bajo muestra badge y alerta roja.
- [ ] Registrar lote → stock sube → alerta desaparece si supera el mínimo.
- [ ] Lote con vencimiento < 30 días aparece en "por vencer" con días en color.
- [ ] Completar un tratamiento con insumos (ficha → plan de tratamiento) descuenta stock.

## Reportes
- [ ] Ingresos reflejan los cobros del período; el rango de fechas filtra.
- [ ] Morosidad lista al paciente con cuota vencida; "Bloquea" correcto según umbral.
- [ ] Producción por doctor cuenta las citas completadas.
- [ ] Descargas Excel (pacientes, inventario) abren bien en Excel/LibreOffice.

## Configuración
- [ ] Crear tratamiento → aparece en Pagos al armar presupuesto.
- [ ] Editar parámetro "dias_morosidad" → el bloqueo de agenda respeta el nuevo valor.
- [ ] Especialidad duplicada → error claro.

## Dashboard
- [ ] Indicadores correctos para el rol; tarjetas rojas cuando corresponde.
- [ ] "Agenda de hoy" coincide con la Agenda.
- [ ] Acciones rápidas navegan bien.

## Robustez general
- [ ] Recargar (F5) en cualquier página mantiene la sesión.
- [ ] Abrir el panel en una pestaña nueva ya logueado no pide login.
- [ ] Sin conexión con el backend (parar django-api) → mensajes de error, no pantallas rotas.
