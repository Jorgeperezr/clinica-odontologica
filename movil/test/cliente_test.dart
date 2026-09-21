/// El cliente: errores legibles y un solo refresco.
library;

import 'dart:convert';

import 'package:clinica_paciente/api/cliente.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// Almacén en memoria: `flutter_secure_storage` necesita Keychain o
/// Keystore, que en una prueba de escritorio no existen.
class _SesionFalsa implements Sesion {
  String? _acceso;
  String? _refresco;

  @override
  Future<String?> get acceso async => _acceso;

  @override
  Future<String?> get refresco async => _refresco;

  @override
  Future<void> guardar(String acceso, String? refresco) async {
    _acceso = acceso;
    if (refresco != null) _refresco = refresco;
  }

  @override
  Future<void> borrar() async {
    _acceso = null;
    _refresco = null;
  }

  @override
  Future<bool> get hayTokens async => _acceso != null;

  @override
  dynamic noSuchMethod(Invocation i) => super.noSuchMethod(i);
}

void main() {
  group('Mensajes de error que una persona pueda leer', () {
    test('el envoltorio de la API: error.message', () {
      final cuerpo = jsonEncode({
        'error': {'code': 'x', 'message': 'La clínica está desactivada.', 'details': {}},
      });
      expect(mensajeDeError(403, cuerpo), 'La clínica está desactivada.');
    });

    test('los errores por campo mandan sobre el mensaje general', () {
      final cuerpo = jsonEncode({
        'error': {
          'message': 'Datos inválidos.',
          'details': {'phone': ['Ese número no está registrado.']},
        },
      });
      expect(mensajeDeError(400, cuerpo), 'Ese número no está registrado.');
    });

    test('el `detail` de DRF', () {
      expect(mensajeDeError(400, jsonEncode({'detail': 'Teléfono o código inválido.'})),
          'Teléfono o código inválido.');
    });

    test('el 429 se explica en vez de soltar un número', () {
      expect(mensajeDeError(429, '{}'), contains('Espera un momento'));
    });

    test('un cuerpo que no es JSON no tumba la app', () {
      // Una página de error de nginx, por ejemplo.
      expect(mensajeDeError(502, '<html>Bad Gateway</html>'), contains('502'));
    });
  });

  group('Refresco del token', () {
    test('varias peticiones que chocan con un 401 refrescan UNA sola vez', () async {
      // Importa porque el backend rota el `refresh` en cada uso: si cada
      // petición pidiera el suyo, la primera invalidaría el de las demás
      // y la sesión se caería sola nada más abrir la app.
      var refrescos = 0;
      var peticiones = 0;

      final falso = MockClient((req) async {
        if (req.url.path.endsWith('/auth/token/refresh/')) {
          refrescos++;
          return http.Response(
              jsonEncode({'access': 'nuevo', 'refresh': 'nuevo-r'}), 200);
        }
        peticiones++;
        final token = req.headers['Authorization'];
        if (token == 'Bearer viejo') return http.Response('{"detail":"caducado"}', 401);
        return http.Response(jsonEncode({'ok': true}), 200);
      });

      final sesion = _SesionFalsa();
      await sesion.guardar('viejo', 'viejo-r');
      final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

      await Future.wait([
        api.objeto('/app/me/'),
        api.objeto('/app/citas/'),
        api.objeto('/app/saldo/'),
        api.objeto('/app/indicaciones/'),
      ]);

      expect(refrescos, 1, reason: 'cada petición pidió su propio refresco');
      expect(await sesion.acceso, 'nuevo');
      // Cuatro que fallan + cuatro reintentos.
      expect(peticiones, 8);
    });

    test('sin refresh guardado, la sesión se borra y se avisa', () async {
      final falso = MockClient((req) async => http.Response('{"detail":"no"}', 401));
      final sesion = _SesionFalsa();
      await sesion.guardar('viejo', null);
      final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

      await expectLater(
        api.objeto('/app/me/'),
        throwsA(isA<ErrorDeApi>().having((e) => e.sesionCaducada, 'caducada', isTrue)),
      );
      expect(await sesion.hayTokens, isFalse);
    });

    test('entrar por OTP deja los dos tokens guardados', () async {
      final falso = MockClient((req) async => http.Response(
          jsonEncode({'access': 'a', 'refresh': 'r', 'role': 'patient'}), 200));
      final sesion = _SesionFalsa();
      final api = ClienteApi(urlBase: 'http://x', sesion: sesion, http_: falso);

      await api.verificarCodigo('+593999111222', '123456');
      expect(await sesion.acceso, 'a');
      expect(await sesion.refresco, 'r');
    });
  });
}
