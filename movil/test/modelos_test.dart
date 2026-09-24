/// Que la app entienda lo que la API manda DE VERDAD.
///
/// Los ficheros de `fixtures/` no están escritos a mano: son respuestas
/// capturadas contra la API en marcha, entrando por el mismo OTP que usa
/// la app. Por eso estas pruebas valen para algo — comprueban el
/// contrato real, no el que yo recuerde—. Si alguien renombra un campo
/// en `apps/app_paciente/views.py`, esto se pone rojo en vez de que un
/// paciente vea un hueco en blanco en su teléfono.
library;

import 'dart:convert';
import 'dart:io';

import 'package:clinica_paciente/api/modelos.dart';
import 'package:clinica_paciente/tema.dart';
import 'package:flutter_test/flutter_test.dart';

Map<String, dynamic> _objeto(String nombre) =>
    jsonDecode(File('test/fixtures/$nombre.json').readAsStringSync())
        as Map<String, dynamic>;

List<dynamic> _lista(String nombre) =>
    jsonDecode(File('test/fixtures/$nombre.json').readAsStringSync())
        as List<dynamic>;

void main() {
  group('Perfil, tal como lo devuelve /app/me/', () {
    late Perfil p;
    setUp(() => p = Perfil.desdeJson(_objeto('me')));

    test('lee el nombre y la clínica', () {
      expect(p.nombre, 'Ana Probe');
      expect(p.clinica, startsWith('Clínica Probe'));
    });

    test('el saldo se queda como cadena', () {
      // Viene de un Decimal de Python. Convertirlo a double para volver
      // a pintarlo es como salen las facturas descuadradas por un centavo.
      expect(p.saldo, '120.00');
      expect(p.saldo, isA<String>());
    });

    test('distingue deber de estar en mora', () {
      expect(p.cuotasPendientes, 2);
      expect(p.cuotasVencidas, 1);
      expect(p.tieneDeuda, isTrue);
      expect(p.estaEnMora, isTrue);
    });

    test('un paciente particular no tiene convenio, y eso no es un fallo', () {
      expect(p.convenio, isNull);
    });

    test('la próxima cita llega anidada y se lee entera', () {
      expect(p.proximaCita, isNotNull);
      expect(p.proximaCita!.motivo, 'Profilaxis dental');
      expect(p.proximaCita!.doctor, 'Dra. Probe');
    });

    test('el estado viene ya traducido por el servidor', () {
      // La app NO mantiene su propia tabla de estados: se
      // desincronizaría en cuanto el backend añadiera uno.
      expect(p.proximaCita!.estado, 'Confirmada');
    });
  });

  group('Agenda, tal como la devuelve /app/citas/', () {
    late Agenda a;
    setUp(() => a = Agenda.desdeJson(_objeto('citas')));

    test('separa próximas de anteriores', () {
      expect(a.proximas, hasLength(1));
      expect(a.anteriores, hasLength(1));
      expect(a.vacia, isFalse);
    });

    test('la próxima es posterior a la anterior', () {
      expect(a.proximas.first.inicio.isAfter(a.anteriores.first.inicio), isTrue);
    });

    test('las horas se pasan a la del teléfono', () {
      // El servidor manda UTC con desfase; al paciente le importa la
      // hora a la que tiene que estar en la clínica.
      expect(a.proximas.first.inicio.isUtc, isFalse);
    });
  });

  group('Estado de cuenta, tal como lo devuelve /app/saldo/', () {
    late EstadoDeCuenta e;
    setUp(() => e = EstadoDeCuenta.desdeJson(_objeto('saldo')));

    test('lee el total y las cuotas', () {
      expect(e.saldoTotal, '120.00');
      expect(e.cuotas, hasLength(2));
    });

    test('la mora la decide el servidor, no el reloj del teléfono', () {
      // Alguien de viaje en otro huso no debe ver una cuota vencida un
      // día antes de estarlo: `vencida` se compara contra la fecha de
      // la clínica, en el servidor.
      expect(e.cuotas.first.vencida, isTrue);
      expect(e.cuotas.last.vencida, isFalse);
      expect(e.alDia, isFalse);
    });

    test('la fecha de vencimiento no se corre de día', () {
      // `vence` es una fecha suelta, sin hora ni huso: si se le
      // aplicara `toLocal()` acabaría siendo el día anterior en
      // Ecuador (UTC-5).
      final c = e.cuotas.first;
      expect('${c.vence.year}-${c.vence.month}-${c.vence.day}', '2026-9-10');
    });

    test('los importes siguen siendo cadenas', () {
      expect(e.cuotas.first.monto, '60.00');
      expect(e.cuotas.first.saldo, '60.00');
    });
  });

  group('Indicaciones, tal como las devuelve /app/indicaciones/', () {
    late List<Indicacion> lista;
    setUp(() => lista = _lista('indicaciones')
        .map((e) => Indicacion.desdeJson(e as Map<String, dynamic>))
        .toList());

    test('llegan las dos visibles', () {
      expect(lista, hasLength(2));
      expect(lista.map((i) => i.tipo),
          containsAll(<String>['Receta', 'Indicación de cuidado']));
    });

    test('la nota clínica interna NO sale de la clínica', () {
      // En la base hay una tercera evolución, de tipo `clinical_note` y
      // marcada como visible. La lista blanca de tipos del servidor la
      // deja fuera, y esto lo comprueba desde el lado del paciente.
      for (final i in lista) {
        expect(i.texto, isNot(contains('NOTA INTERNA')));
      }
    });

    test('se lee el texto y quién lo firma', () {
      final receta = lista.firstWhere((i) => i.tipo == 'Receta');
      expect(receta.texto, contains('Amoxicilina'));
      expect(receta.profesional, 'Dra. Probe');
    });
  });

  _pruebasDeLogros();
  _pruebasDeMarca();

  group('Lo que puede faltar no debe romper la app', () {
    test('una cita sin tratamiento ni doctor se lee igual', () {
      final c = Cita.desdeJson({
        'id': 'x',
        'inicio': '2026-09-24T03:23:27.285677+00:00',
        'fin': '2026-09-24T04:08:27.285677+00:00',
        'estado': 'Pendiente',
        'doctor': null,
        'motivo': null,
      });
      expect(c.doctor, isNull);
      expect(c.motivo, isNull);
    });

    test('un perfil sin próxima cita ni deuda', () {
      final p = Perfil.desdeJson({
        'nombre': 'Solo Nombre',
        'clinica': 'C',
        'cuotas_pendientes': 0,
        'cuotas_vencidas': 0,
        'saldo': '0',
        'proxima_cita': null,
      });
      expect(p.proximaCita, isNull);
      expect(p.tieneDeuda, isFalse);
      expect(p.estaEnMora, isFalse);
    });

    test('una agenda vacía se reconoce como vacía', () {
      final a = Agenda.desdeJson({'proximas': [], 'anteriores': []});
      expect(a.vacia, isTrue);
    });
  });
}

// ── Rachas y logros ──────────────────────────────────────────────────

void _pruebasDeLogros() {
  group('Logros, tal como los devuelve /app/logros/', () {
    late List<Logro> lista;
    setUp(() => lista = _lista('logros')
        .map((e) => Logro.desdeJson(e as Map<String, dynamic>))
        .toList());

    test('llegan los dos', () {
      expect(lista, hasLength(2));
    });

    test('una racha de tres meses se reconoce como racha', () {
      final constancia = lista.firstWhere((l) => l.nombre == 'Constancia');
      expect(constancia.racha, 3);
      expect(constancia.veces, 3);
      expect(constancia.esRacha, isTrue);
      expect(constancia.automatico, isTrue);
    });

    test('un logro suelto NO es una racha', () {
      // `racha` vale 0 en los manuales, que no tienen periodo. Sin esta
      // distinción, la app pintaría el anillo de llama y el contador de
      // meses en algo que se ganó una sola vez.
      final manual = lista.firstWhere((l) => l.nombre == 'Cuidado impecable');
      expect(manual.racha, 0);
      expect(manual.esRacha, isFalse);
      expect(manual.automatico, isFalse);
    });

    test('el beneficio llega para poder enseñarlo', () {
      final constancia = lista.firstWhere((l) => l.nombre == 'Constancia');
      expect(constancia.tieneBeneficio, isTrue);
      expect(constancia.beneficio, contains('10%'));
    });

    test('un logro sin beneficio no finge tenerlo', () {
      final sin = Logro.desdeJson({
        'id': 'x', 'nombre': 'Simple', 'icono': 'estrella',
        'obtenido': '2026-09-22', 'veces': 1, 'racha': 0,
        'automatico': false, 'beneficio': '   ',
      });
      expect(sin.tieneBeneficio, isFalse);
    });

    test('un icono desconocido no deja un hueco', () {
      // La clínica puede inventarse claves nuevas; la app cae en la
      // estrella en vez de romperse o dejar el círculo vacío.
      expect(iconoDeLogro('algo_que_no_existe'), iconoDeLogro('estrella'));
    });
  });
}

// ── La marca de la clínica ───────────────────────────────────────────

void _pruebasDeMarca() {
  group('Marca de la clínica', () {
    test('lee lo que devuelve /app/clinica/', () {
      final m = Marca.desdeJson({
        'nombre': 'Sonrisa Feliz',
        'nombre_corto': 'Sonrisa',
        'logo': 'http://localhost:8000/media/branding/logos/x.png',
        'color_principal': '#0e5c63',
        'color_secundario': '#9fe1cb',
        'telefono': '02 244 8890',
        'direccion': 'Av. Amazonas N34-120',
        'email': 'hola@sonrisa.ec',
      });
      expect(m.nombre, 'Sonrisa Feliz');
      expect(m.nombreDeBarra, 'Sonrisa');
      expect(m.tieneLogo, isTrue);
      expect(m.sePuedeLlamar, isTrue);
      expect(m.colorPrincipal, 0xFF0E5C63);
    });

    test('sin nombre corto, la barra usa el largo', () {
      final m = Marca.desdeJson({
        'nombre': 'Clínica Larga', 'nombre_corto': '   ',
        'color_principal': '#14639e', 'color_secundario': '#bcdcf2',
      });
      expect(m.nombreDeBarra, 'Clínica Larga');
    });

    test('un color corrupto no deja la app negra', () {
      // Un entero mal parseado pintaría la app de negro o reventaría al
      // construir el ColorScheme.
      for (final malo in ['azul', '#zzz', '', '0e5c63', '#0e5c6']) {
        expect(colorDesdeHex(malo, 0xFF14639E), 0xFF14639E, reason: malo);
      }
    });

    test('un logo vacío es no tener logo', () {
      final m = Marca.desdeJson({
        'nombre': 'X', 'logo': '   ',
        'color_principal': '#14639e', 'color_secundario': '#bcdcf2',
      });
      expect(m.tieneLogo, isFalse);
    });

    test('sin nombre se usa el neutro en vez de dejar la barra vacía', () {
      final m = Marca.desdeJson({
        'nombre': '', 'color_principal': '#14639e', 'color_secundario': '#bcdcf2',
      });
      expect(m.nombre, Marca.neutra.nombre);
    });

    test('guardar y volver a leer conserva los colores', () {
      // Es lo que evita el parpadeo al arrancar: la marca se guarda y
      // se relee antes de pintar la primera pantalla.
      const original = Marca(
        nombre: 'Sonrisa', colorPrincipal: 0xFF0E5C63,
        colorSecundario: 0xFF9FE1CB, telefono: '099');
      final ida = Marca.desdeJson(original.aJson());
      expect(ida.colorPrincipal, original.colorPrincipal);
      expect(ida.colorSecundario, original.colorSecundario);
      expect(ida.telefono, '099');
    });
  });

  group('Solicitudes de cita, tal como las devuelve /app/solicitudes-cita/', () {
    late List<SolicitudCita> s;
    setUp(() => s = _lista('solicitudes-cita')
        .map((e) => SolicitudCita.desdeJson(e as Map<String, dynamic>))
        .toList());

    test('llegan los tres estados', () {
      expect(s.map((x) => x.estado).toSet(), {'pendiente', 'rechazada', 'agendada'});
      expect(s.where((x) => x.pendiente).length, 1);
    });

    test('un rechazo trae siempre la explicación de la clínica', () {
      final r = s.firstWhere((x) => x.estado == 'rechazada');
      expect(r.respuesta, isNotEmpty);
      expect(r.estadoTexto, 'No se pudo agendar');
      expect(r.citaInicio, isNull);
    });

    test('la agendada trae la hora de la cita, pasada a la hora del teléfono', () {
      final a = s.firstWhere((x) => x.estado == 'agendada');
      expect(a.citaInicio, isNotNull);
      expect(a.citaInicio!.isUtc, isFalse);
      expect(a.citaInicio!.toUtc(), DateTime.utc(2026, 9, 26, 14, 30));
    });

    test('la fecha preferida es un día, sin hora que se pueda correr', () {
      for (final x in s) {
        expect(x.fechaPreferida.hour, 0);
      }
    });
  });

  group('Mensajes, tal como los devuelve /app/mensajes/', () {
    late List<MensajeConsultorio> m;
    setUp(() => m = _lista('mensajes')
        .map((e) => MensajeConsultorio.desdeJson(e as Map<String, dynamic>))
        .toList());

    test('uno con respuesta y otro esperando', () {
      expect(m.where((x) => x.tieneRespuesta).length, 1);
      expect(m.where((x) => !x.tieneRespuesta).length, 1);
      expect(m.firstWhere((x) => x.tieneRespuesta).respuesta, contains('400 mg'));
      expect(m.firstWhere((x) => !x.tieneRespuesta).respuesta, isEmpty);
    });
  });
}

