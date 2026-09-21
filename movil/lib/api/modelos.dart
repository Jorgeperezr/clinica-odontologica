/// Lo que devuelve la API del paciente, en objetos de Dart.
///
/// Las formas NO están supuestas: salen de respuestas reales capturadas
/// contra la API en marcha, y esas mismas capturas están en
/// `test/fixtures/` como prueba. Si el backend cambia un nombre de
/// campo, el test se pone rojo aquí en vez de que la app enseñe un
/// hueco en blanco en el teléfono de alguien.
///
/// Dos decisiones que se repiten en todo el archivo:
///
///   · **El dinero llega como cadena** (`"120.00"`) porque viene de un
///     `Decimal` de Python, y se queda como cadena. Pasarlo a `double`
///     para volver a pintarlo es invitar a que 0.1 + 0.2 salga en una
///     factura.
///   · **Casi todo puede venir nulo.** Una cita sin tratamiento no tiene
///     `motivo`; un paciente particular no tiene `convenio`. Se modela
///     como nulo en vez de con cadena vacía, para que la pantalla
///     decida qué enseñar.
library;

/// Una cita como la ve el paciente (sin notas internas de la clínica).
class Cita {
  const Cita({
    required this.id,
    required this.inicio,
    required this.fin,
    required this.estado,
    this.doctor,
    this.motivo,
  });

  final String id;
  final DateTime inicio;
  final DateTime fin;

  /// Ya viene traducido del servidor («Confirmada», «Completada»): la
  /// app NO mantiene su propia tabla de estados, que se desincronizaría
  /// en cuanto el backend añadiera uno.
  final String estado;
  final String? doctor;
  final String? motivo;

  factory Cita.desdeJson(Map<String, dynamic> j) => Cita(
        id: j['id'] as String,
        // `toLocal()` porque el servidor manda UTC con desfase y el
        // paciente piensa en la hora a la que tiene que estar allí.
        inicio: DateTime.parse(j['inicio'] as String).toLocal(),
        fin: DateTime.parse(j['fin'] as String).toLocal(),
        estado: j['estado'] as String? ?? '',
        doctor: j['doctor'] as String?,
        motivo: j['motivo'] as String?,
      );
}

/// La pantalla de inicio: lo justo para saber cómo se está.
class Perfil {
  const Perfil({
    required this.nombre,
    required this.clinica,
    required this.cuotasPendientes,
    required this.cuotasVencidas,
    required this.saldo,
    this.cedula,
    this.convenio,
    this.proximaCita,
  });

  final String nombre;
  final String clinica;
  final int cuotasPendientes;
  final int cuotasVencidas;
  final String saldo;
  final String? cedula;
  final String? convenio;
  final Cita? proximaCita;

  bool get tieneDeuda => cuotasPendientes > 0;
  bool get estaEnMora => cuotasVencidas > 0;

  factory Perfil.desdeJson(Map<String, dynamic> j) => Perfil(
        nombre: j['nombre'] as String? ?? '',
        clinica: j['clinica'] as String? ?? '',
        cuotasPendientes: (j['cuotas_pendientes'] as num?)?.toInt() ?? 0,
        cuotasVencidas: (j['cuotas_vencidas'] as num?)?.toInt() ?? 0,
        saldo: j['saldo'] as String? ?? '0',
        cedula: j['cedula'] as String?,
        convenio: j['convenio'] as String?,
        proximaCita: j['proxima_cita'] == null
            ? null
            : Cita.desdeJson(j['proxima_cita'] as Map<String, dynamic>),
      );
}

/// Las citas separadas como las manda el servidor.
class Agenda {
  const Agenda({required this.proximas, required this.anteriores});

  final List<Cita> proximas;
  final List<Cita> anteriores;

  bool get vacia => proximas.isEmpty && anteriores.isEmpty;

  factory Agenda.desdeJson(Map<String, dynamic> j) => Agenda(
        proximas: _lista(j['proximas']),
        anteriores: _lista(j['anteriores']),
      );

  static List<Cita> _lista(Object? bruto) => (bruto as List<dynamic>? ?? [])
      .map((e) => Cita.desdeJson(e as Map<String, dynamic>))
      .toList();
}

/// Una cuota del plan de pago.
class Cuota {
  const Cuota({
    required this.numero,
    required this.vence,
    required this.monto,
    required this.pagado,
    required this.saldo,
    required this.estado,
    required this.vencida,
  });

  final int numero;
  final DateTime vence;
  final String monto;
  final String pagado;
  final String saldo;
  final String estado;

  /// Lo decide el SERVIDOR comparando con la fecha de la clínica, que no
  /// tiene por qué ser la del teléfono: alguien de viaje en otro huso no
  /// debe ver una cuota en mora un día antes de estarlo.
  final bool vencida;

  factory Cuota.desdeJson(Map<String, dynamic> j) => Cuota(
        numero: (j['numero'] as num).toInt(),
        // `vence` es una fecha suelta («2026-09-10»), sin hora ni huso:
        // NO se le aplica `toLocal()`, que la correría un día según
        // dónde esté el teléfono.
        vence: DateTime.parse(j['vence'] as String),
        monto: j['monto'] as String? ?? '0',
        pagado: j['pagado'] as String? ?? '0',
        saldo: j['saldo'] as String? ?? '0',
        estado: j['estado'] as String? ?? '',
        vencida: j['vencida'] as bool? ?? false,
      );
}

/// El estado de cuenta completo.
class EstadoDeCuenta {
  const EstadoDeCuenta({required this.saldoTotal, required this.cuotas});

  final String saldoTotal;
  final List<Cuota> cuotas;

  bool get alDia => cuotas.every((c) => !c.vencida);

  factory EstadoDeCuenta.desdeJson(Map<String, dynamic> j) => EstadoDeCuenta(
        saldoTotal: j['saldo_total'] as String? ?? '0',
        cuotas: (j['cuotas'] as List<dynamic>? ?? [])
            .map((e) => Cuota.desdeJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// Una receta o una indicación de cuidado.
class Indicacion {
  const Indicacion({
    required this.id,
    required this.tipo,
    required this.fecha,
    required this.texto,
    this.profesional,
  });

  final String id;

  /// «Receta» o «Indicación de cuidado», ya traducido por el servidor.
  final String tipo;
  final DateTime fecha;
  final String texto;
  final String? profesional;

  factory Indicacion.desdeJson(Map<String, dynamic> j) => Indicacion(
        id: j['id'] as String,
        tipo: j['tipo'] as String? ?? '',
        fecha: DateTime.parse(j['fecha'] as String),
        texto: j['texto'] as String? ?? '',
        profesional: j['profesional'] as String?,
      );
}
