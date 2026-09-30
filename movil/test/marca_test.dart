/// La marca de Clinube en la app: el logotipo, la paleta por omisión y
/// el ajuste «Sin color».
library;

import 'dart:io';

import 'package:clinube/api/cliente.dart';
import 'package:clinube/api/modelos.dart';
import 'package:clinube/logo.dart';
import 'package:clinube/pantallas/ingreso.dart';
import 'package:clinube/pantallas/perfil.dart';
import 'package:clinube/tema.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'sesion_falsa.dart';

String _fixture(String n) => File('test/fixtures/$n.json').readAsStringSync();

Future<ClienteApi> _api() async {
  final sesion = SesionFalsa();
  await sesion.guardar('a', 'r');
  return ClienteApi(
    urlBase: 'http://x',
    sesion: sesion,
    http_: MockClient((req) async => http.Response(
        _fixture(req.url.path.endsWith('/logros/') ? 'logros' : 'me'), 200,
        headers: {'content-type': 'application/json; charset=utf-8'})),
  );
}

void main() {
  setUpAll(() async => initializeDateFormatting('es'));

  group('logotipo', () {
    test('los trazados se leen: M, L, Q y Z', () {
      final p = trazado('M0 0L10 0Q10 10 0 10Z');
      expect(p.getBounds(), const Rect.fromLTRB(0, 0, 10, 10));
    });

    test('una orden desconocida se dice, no se dibuja un garabato', () {
      expect(() => trazado('M0 0C1 1 2 2 3 3'), throwsFormatException);
    });

    testWidgets('se dibuja con la proporción de la palabra', (tester) async {
      await tester.pumpWidget(const MaterialApp(
          home: Center(child: LogoClinube(alto: 40))));
      final tam = tester.getSize(find.byType(CustomPaint).last);
      expect(tam.height, 40);
      // «clinube» es unas 4,4 veces más ancho que alto.
      expect(tam.width / tam.height, closeTo(4.45, 0.05));
      expect(tester.takeException(), isNull);
    });

    testWidgets('una clínica sin logotipo lleva el de Clinube al ingresar',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
          home: PantallaIngreso(api: await _api(), alEntrar: () {})));
      expect(find.byType(LogoClinube), findsOneWidget);
    });
  });

  group('paleta', () {
    test('toda clínica empieza con la de Clinube', () {
      expect(Marca.neutra.colorPrincipal, 0xFF0E7490);
      expect(Marca.neutra.esEnGrises, isFalse);
    });

    test('«Sin color» elegido por la clínica se reconoce por ser gris', () {
      final m = Marca.desdeJson(
          {'nombre': 'X', 'color_principal': '#404040', 'color_secundario': '#9ca3af'});
      expect(m.esEnGrises, isTrue);
    });

    test('sin color, el tema y los anillos son grises de verdad', () {
      final gris = temaClaro(0xFF0E7490, true);
      expect(esGris(gris.colorScheme.primary.toARGB32()), isTrue);
      expect(gris.extension<Anillos>(), Anillos.enGrises);

      final conColor = temaClaro(0xFF0E7490);
      expect(esGris(conColor.colorScheme.primary.toARGB32()), isFalse);
      expect(conColor.extension<Anillos>(), Anillos.conColor);
    });
  });

  group('ajuste «Sin color» en el perfil', () {
    Future<SwitchListTile> interruptor(WidgetTester tester) async {
      final f = find.byType(SwitchListTile);
      await tester.scrollUntilVisible(f, 200,
          scrollable: find.byType(Scrollable).first);
      return tester.widget<SwitchListTile>(f);
    }

    testWidgets('se enciende desde el perfil', (tester) async {
      bool? pedido;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PantallaPerfil(
            api: await _api(),
            alSalir: () {},
            alCambiarSinColor: (v) => pedido = v,
          ),
        ),
      ));
      await tester.pumpAndSettle();

      expect((await interruptor(tester)).value, isFalse);
      await tester.tap(find.byType(SwitchListTile));
      expect(pedido, isTrue);
    });

    testWidgets('si la clínica ya es «Sin color», no finge poder cambiarlo',
        (tester) async {
      const gris = Marca(
          nombre: 'En grises',
          colorPrincipal: 0xFF404040,
          colorSecundario: 0xFF9CA3AF);
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PantallaPerfil(
            api: await _api(),
            alSalir: () {},
            marca: gris,
            alCambiarSinColor: (_) {},
          ),
        ),
      ));
      await tester.pumpAndSettle();

      final s = await interruptor(tester);
      expect(s.value, isTrue);
      expect(s.onChanged, isNull);
      expect(find.text('Tu clínica ya usa la versión sin color.'), findsOneWidget);
    });
  });
}
