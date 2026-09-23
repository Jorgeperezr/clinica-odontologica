/// Que la interfaz se construya de verdad.
///
/// Sustituye al test de plantilla que deja `flutter create`, que apunta
/// a una clase `MyApp` que aquí no existe.
///
/// Es la única prueba que monta widgets, y cubre lo que las de modelos
/// no pueden: que el árbol se construya sin reventar y que las pantallas
/// digan lo que tienen que decir. Sin esto, un fallo tonto de layout
/// solo aparecería al abrir la app en un teléfono.
library;

import 'dart:convert';

import 'package:clinica_paciente/api/cliente.dart';
import 'package:clinica_paciente/api/modelos.dart';
import 'package:clinica_paciente/pantallas/ingreso.dart';
import 'package:clinica_paciente/pantallas/principal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'sesion_falsa.dart';

Widget _envoltorio(Widget hijo) => MaterialApp(home: hijo);

void main() {
  setUpAll(() async {
    // Sin esto, `DateFormat` con 'es' lanza al pintar la primera fecha.
    await initializeDateFormatting('es');
  });

  testWidgets('el ingreso pide primero el teléfono y luego el código',
      (tester) async {
    final falso = MockClient((req) async => http.Response('{}', 200));
    final api = ClienteApi(
        urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaIngreso(api: api, alEntrar: () {}),
    ));

    expect(find.text('Enviarme el código'), findsOneWidget);
    expect(find.text('Código de 6 dígitos'), findsNothing);

    await tester.enterText(find.byType(TextField).first, '+593999111222');
    await tester.tap(find.text('Enviarme el código'));
    await tester.pumpAndSettle();

    expect(find.text('Código de 6 dígitos'), findsOneWidget);
    expect(find.text('Entrar'), findsOneWidget);
  });

  testWidgets('un teléfono no registrado se explica, no se traga',
      (tester) async {
    final falso = MockClient((req) async => http.Response(
        jsonEncode({'detail': 'Ese número no está registrado.'}), 400));
    final api = ClienteApi(
        urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaIngreso(api: api, alEntrar: () {}),
    ));
    await tester.enterText(find.byType(TextField).first, '+593000000000');
    await tester.tap(find.text('Enviarme el código'));
    await tester.pumpAndSettle();

    expect(find.text('Ese número no está registrado.'), findsOneWidget);
    // Y NO avanza al paso del código: no habría ninguno que meter.
    expect(find.text('Código de 6 dígitos'), findsNothing);
  });

  testWidgets('el inicio pinta los datos que devuelve la API',
      (tester) async {
    final falso = MockClient((req) async {
      if (req.url.path.endsWith('/app/me/')) {
        return http.Response(
            jsonEncode({
              'nombre': 'Ana Probe',
              'cedula': '1723456789',
              'clinica': 'Clínica Probe',
              'convenio': null,
              'proxima_cita': {
                'id': 'c1',
                'inicio': '2026-09-24T13:00:00+00:00',
                'fin': '2026-09-24T13:45:00+00:00',
                'estado': 'Confirmada',
                'doctor': 'Dra. Probe',
                'motivo': 'Profilaxis dental',
              },
              'cuotas_pendientes': 2,
              'cuotas_vencidas': 1,
              'saldo': '120.00',
            }),
            200);
      }
      if (req.url.path.endsWith('/app/logros/')) {
        return http.Response(
            jsonEncode([
              {
                'id': 'l1',
                'nombre': 'Constancia',
                'descripcion': 'Asististe a todas tus citas del mes.',
                'icono': 'racha',
                'beneficio': '10% en tu próxima profilaxis.',
                'obtenido': '2026-09-22',
                'veces': 3,
                'racha': 3,
                'automatico': true,
              }
            ]),
            200);
      }
      return http.Response('{}', 200);
    });
    final sesion = SesionFalsa();
    await sesion.guardar('t', 'r');
    final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaPrincipal(api: api, alSalir: () {}),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Hola, Ana'), findsOneWidget);
    expect(find.text('Profilaxis dental'), findsOneWidget);
    // El saldo se pinta tal cual llega, sin pasar por `double`.
    expect(find.textContaining('120.00'), findsOneWidget);
    expect(find.textContaining('1 cuota vencida'), findsOneWidget);
    // La fila de logros, con el contador de meses de la racha.
    expect(find.text('Constancia'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
  });

  testWidgets('tocar un logro abre su beneficio', (tester) async {
    // Es la razón de ser de la pantalla: el paciente tiene que poder
    // llegar a lo que ha ganado sin buscarlo.
    final falso = MockClient((req) async {
      if (req.url.path.endsWith('/app/logros/')) {
        return http.Response(
            jsonEncode([
              {
                'id': 'l1',
                'nombre': 'Constancia',
                'descripcion': 'Asististe a todas tus citas del mes.',
                'icono': 'racha',
                'beneficio': '10% en tu próxima profilaxis.',
                'obtenido': '2026-09-22',
                'veces': 3,
                'racha': 3,
                'automatico': true,
              }
            ]),
            200);
      }
      return http.Response(
          jsonEncode({
            'nombre': 'Ana Probe',
            'clinica': 'Clínica Probe',
            'cuotas_pendientes': 0,
            'cuotas_vencidas': 0,
            'saldo': '0',
            'proxima_cita': null,
          }),
          200);
    });
    final sesion = SesionFalsa();
    await sesion.guardar('t', 'r');
    final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaPrincipal(api: api, alSalir: () {}),
    ));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Constancia'));
    await tester.pumpAndSettle();

    expect(find.text('3 meses seguidos'), findsOneWidget);
    expect(find.text('Tu beneficio'), findsOneWidget);
    expect(find.textContaining('10% en tu próxima profilaxis'), findsOneWidget);
    // Y se dice dónde se cobra: el descuento NO se aplica solo.
    expect(find.textContaining('Recuérdaselo a tu clínica'), findsOneWidget);
  });

  testWidgets('si la API falla, se ve el motivo y un botón de reintentar',
      (tester) async {
    // Lo que NO puede pasar es una pantalla en blanco: un paciente
    // creería que no tiene ninguna cita.
    final falso = MockClient((req) async =>
        http.Response(jsonEncode({'detail': 'La clínica está desactivada.'}), 403));
    final sesion = SesionFalsa();
    await sesion.guardar('t', 'r');
    final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaPrincipal(api: api, alSalir: () {}),
    ));
    await tester.pumpAndSettle();

    expect(find.text('La clínica está desactivada.'), findsOneWidget);
    expect(find.text('Reintentar'), findsOneWidget);
  });

  testWidgets('el ingreso lleva el nombre de la clínica, no uno genérico',
      (tester) async {
    const marca = Marca(
      nombre: 'Sonrisa Feliz',
      colorPrincipal: 0xFF0E5C63,
      colorSecundario: 0xFF9FE1CB,
    );
    final falso = MockClient((req) async => http.Response('{}', 200));
    final api = ClienteApi(
        urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaIngreso(api: api, marca: marca, alEntrar: () {}),
    ));

    expect(find.text('Sonrisa Feliz'), findsOneWidget);
    expect(find.text('Tu clínica'), findsNothing);
  });

  testWidgets('un logotipo que no carga NO deja un aspa rota', (tester) async {
    // El logotipo viene de la red: un servidor caído o una URL vieja
    // dejarían el icono de imagen rota presidiendo el ingreso.
    const marca = Marca(
      nombre: 'Sonrisa Feliz',
      logo: 'http://127.0.0.1:9/no-existe.png',
      colorPrincipal: 0xFF0E5C63,
      colorSecundario: 0xFF9FE1CB,
    );
    final falso = MockClient((req) async => http.Response('{}', 200));
    final api = ClienteApi(
        urlBase: 'http://x', sesion: SesionFalsa(), http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaIngreso(api: api, marca: marca, alEntrar: () {}),
    ));
    await tester.pump(const Duration(seconds: 1));

    // Se cae al icono genérico y la pantalla sigue siendo usable.
    expect(find.text('Sonrisa Feliz'), findsOneWidget);
    expect(find.text('Enviarme el código'), findsOneWidget);
  });

  testWidgets('la barra de dentro lleva el nombre corto', (tester) async {
    const marca = Marca(
      nombre: 'Clínica Odontológica Sonrisa Feliz del Valle',
      nombreCorto: 'Sonrisa',
      colorPrincipal: 0xFF0E5C63,
      colorSecundario: 0xFF9FE1CB,
    );
    final falso = MockClient((req) async {
      if (req.url.path.endsWith('/app/logros/')) {
        return http.Response('[]', 200);
      }
      return http.Response(
          jsonEncode({
            'nombre': 'Ana Probe', 'clinica': 'Sonrisa Feliz',
            'cuotas_pendientes': 0, 'cuotas_vencidas': 0,
            'saldo': '0', 'proxima_cita': null,
          }),
          200);
    });
    final sesion = SesionFalsa();
    await sesion.guardar('t', 'r');
    final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

    await tester.pumpWidget(_envoltorio(
      PantallaPrincipal(api: api, marca: marca, alSalir: () {}),
    ));
    await tester.pumpAndSettle();

    // El nombre largo no cabe en una barra de teléfono; por eso existe
    // el corto y por eso la barra lo prefiere.
    expect(find.text('Sonrisa'), findsOneWidget);
  });
}
