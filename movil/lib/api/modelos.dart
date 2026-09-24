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

/// Una racha o un logro que el paciente ya ganó.
///
/// Es lo CONCEDIDO, no lo que cumpliría hoy: un logro es un hecho con su
/// fecha. Recalcularlo al leerlo haría que alguien perdiera una medalla
/// por faltar a una cita este mes, que es lo contrario de fidelizar.
class Logro {
  const Logro({
    required this.id,
    required this.nombre,
    required this.icono,
    required this.obtenido,
    required this.veces,
    required this.racha,
    required this.automatico,
    this.descripcion = '',
    this.beneficio = '',
  });

  final String id;
  final String nombre;

  /// Clave corta, no una imagen: la app elige el icono. Así cambiar el
  /// aspecto no obliga a resubir nada al servidor.
  final String icono;
  final DateTime obtenido;

  /// Cuántas veces lo ha ganado en total.
  final int veces;

  /// Meses seguidos. Es lo que se enseña como «3 meses seguidos».
  final int racha;
  final bool automatico;
  final String descripcion;
  final String beneficio;

  bool get esRacha => racha > 1;
  bool get tieneBeneficio => beneficio.trim().isNotEmpty;

  factory Logro.desdeJson(Map<String, dynamic> j) => Logro(
        id: j['id'] as String,
        nombre: j['nombre'] as String? ?? '',
        icono: j['icono'] as String? ?? 'estrella',
        obtenido: DateTime.parse(j['obtenido'] as String),
        veces: (j['veces'] as num?)?.toInt() ?? 1,
        racha: (j['racha'] as num?)?.toInt() ?? 0,
        automatico: j['automatico'] as bool? ?? false,
        descripcion: j['descripcion'] as String? ?? '',
        beneficio: j['beneficio'] as String? ?? '',
      );
}

/// La identidad de la clínica: cómo se llama, su logotipo y sus colores.
///
/// **Los colores llegan resueltos** en `#rrggbb`. La app no guarda
/// ninguna tabla de temas a propósito: si la guardara, el día que
/// alguien añada un tema en el panel la misma clínica se vería de un
/// color en el escritorio y de otro en el teléfono.
class Marca {
  const Marca({
    required this.nombre,
    required this.colorPrincipal,
    required this.colorSecundario,
    this.nombreCorto = '',
    this.logo,
    this.telefono = '',
    this.direccion = '',
    this.email = '',
  });

  final String nombre;

  /// Enteros ARGB ya parseados: guardarlos como cadena obligaría a
  /// parsear en cada `build`, que ocurre muchas veces por segundo.
  final int colorPrincipal;
  final int colorSecundario;
  final String nombreCorto;

  /// URL absoluta. Nginx publica `/media/branding/` sin token y niega el
  /// resto de `/media/`, así que el logotipo se puede cargar con una
  /// imagen normal y las radiografías siguen protegidas.
  final String? logo;
  final String telefono;
  final String direccion;
  final String email;

  bool get tieneLogo => (logo ?? '').isNotEmpty;
  bool get sePuedeLlamar => telefono.trim().isNotEmpty;

  /// El nombre que cabe en una barra estrecha.
  String get nombreDeBarra => nombreCorto.trim().isNotEmpty ? nombreCorto : nombre;

  /// La marca por omisión, mientras no se sepa de qué clínica se trata
  /// —antes del primer ingreso— o si la petición falla. Nunca se deja la
  /// app sin colores: una pantalla en blanco es peor que unos colores
  /// que no son los de la clínica.
  static const neutra = Marca(
    nombre: 'Tu clínica',
    colorPrincipal: 0xFF14639E,
    colorSecundario: 0xFFBCDCF2,
  );

  factory Marca.desdeJson(Map<String, dynamic> j) => Marca(
        nombre: (j['nombre'] as String? ?? '').trim().isEmpty
            ? neutra.nombre
            : (j['nombre'] as String).trim(),
        nombreCorto: j['nombre_corto'] as String? ?? '',
        logo: (j['logo'] as String?)?.trim().isEmpty ?? true
            ? null
            : (j['logo'] as String).trim(),
        colorPrincipal: colorDesdeHex(j['color_principal'], neutra.colorPrincipal),
        colorSecundario: colorDesdeHex(j['color_secundario'], neutra.colorSecundario),
        telefono: j['telefono'] as String? ?? '',
        direccion: j['direccion'] as String? ?? '',
        email: j['email'] as String? ?? '',
      );

  Map<String, dynamic> aJson() => {
        'nombre': nombre,
        'nombre_corto': nombreCorto,
        'logo': logo,
        'color_principal': '#${(colorPrincipal & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}',
        'color_secundario': '#${(colorSecundario & 0xFFFFFF).toRadixString(16).padLeft(6, '0')}',
        'telefono': telefono,
        'direccion': direccion,
        'email': email,
      };
}

/// `#rrggbb` a entero ARGB. Lo que no encaje cae en `porDefecto`: un
/// color corrupto dejaría la app negra o la haría reventar al pintar.
int colorDesdeHex(Object? valor, int porDefecto) {
  final texto = (valor as String? ?? '').trim();
  if (texto.length != 7 || !texto.startsWith('#')) return porDefecto;
  final n = int.tryParse(texto.substring(1), radix: 16);
  return n == null ? porDefecto : 0xFF000000 | n;
}

/// Una cita que el paciente pidió desde la app. No es una cita todavía:
/// la crea la recepción, que es quien conoce la agenda.
class SolicitudCita {
  const SolicitudCita({
    required this.id,
    required this.fechaPreferida,
    required this.franja,
    required this.franjaTexto,
    required this.motivo,
    required this.estado,
    required this.estadoTexto,
    required this.respuesta,
    required this.creada,
    this.citaInicio,
  });

  final String id;
  final DateTime fechaPreferida;
  final String franja;
  final String franjaTexto;
  final String motivo;

  /// `pendiente`, `agendada` o `rechazada`.
  final String estado;

  /// El estado ya traducido por el servidor («No se pudo agendar»…).
  final String estadoTexto;

  /// Lo que contestó la clínica; en un rechazo, siempre hay algo.
  final String respuesta;
  final DateTime creada;

  /// Cuándo quedó la cita, si se agendó.
  final DateTime? citaInicio;

  bool get pendiente => estado == 'pendiente';

  factory SolicitudCita.desdeJson(Map<String, dynamic> j) {
    final cita = j['cita'] as Map<String, dynamic>?;
    return SolicitudCita(
      id: j['id'] as String,
      // La fecha preferida es un día sin hora: se lee como fecha local.
      fechaPreferida: DateTime.parse(j['fecha_preferida'] as String),
      franja: j['franja'] as String? ?? 'cualquiera',
      franjaTexto: j['franja_texto'] as String? ?? '',
      motivo: j['motivo'] as String? ?? '',
      estado: j['estado'] as String? ?? 'pendiente',
      estadoTexto: j['estado_texto'] as String? ?? '',
      respuesta: j['respuesta'] as String? ?? '',
      creada: DateTime.parse(j['creada'] as String).toLocal(),
      citaInicio: cita == null ? null : DateTime.parse(cita['inicio'] as String).toLocal(),
    );
  }
}

/// Un mensaje del paciente a su clínica, con la respuesta si ya la hay.
class MensajeConsultorio {
  const MensajeConsultorio({
    required this.id,
    required this.texto,
    required this.creado,
    required this.respuesta,
    this.respondido,
  });

  final String id;
  final String texto;
  final DateTime creado;
  final String respuesta;
  final DateTime? respondido;

  bool get tieneRespuesta => respondido != null;

  factory MensajeConsultorio.desdeJson(Map<String, dynamic> j) => MensajeConsultorio(
        id: j['id'] as String,
        texto: j['texto'] as String? ?? '',
        creado: DateTime.parse(j['creado'] as String).toLocal(),
        respuesta: j['respuesta'] as String? ?? '',
        respondido: j['respondido'] == null ? null : DateTime.parse(j['respondido'] as String).toLocal(),
      );
}
