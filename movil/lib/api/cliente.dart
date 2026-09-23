/// Cliente de la API del paciente.
///
/// Dos cosas que este archivo se toma en serio, porque de ellas depende
/// que la app sea usable y que no filtre nada:
///
///   1. **Los tokens no se guardan en claro.** Dan acceso a datos
///      clínicos, así que van al Keychain (iOS) y al Keystore
///      (Android) a través de `flutter_secure_storage`, no a
///      `shared_preferences`, que es un XML legible en un teléfono con
///      root.
///
///   2. **El refresco es de un solo intento y serializado.** Al abrir la
///      app se piden cuatro pantallas a la vez; si el `access` ha
///      caducado, las cuatro fallarían con 401 y cada una pediría su
///      propio refresco. Como el backend rota el `refresh` en cada uso
///      (`ROTATE_REFRESH_TOKENS`), la primera invalidaría el token de las
///      otras tres y la sesión se caería sola. Por eso hay un único
///      `Future` de refresco compartido.
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'modelos.dart';

/// Fallo con un mensaje que se le puede enseñar a una persona.
class ErrorDeApi implements Exception {
  ErrorDeApi(this.mensaje, {this.codigo});

  final String mensaje;
  final int? codigo;

  /// La sesión ya no vale y hay que volver a entrar.
  bool get sesionCaducada => codigo == 401;

  @override
  String toString() => mensaje;
}

/// Guarda y recupera los tokens del almacén seguro del sistema.
class Sesion {
  Sesion({FlutterSecureStorage? almacen})
      : _almacen = almacen ?? const FlutterSecureStorage();

  final FlutterSecureStorage _almacen;

  static const _claveAcceso = 'acceso';
  static const _claveRefresco = 'refresco';
  static const _claveMarca = 'marca';

  Future<String?> get acceso => _almacen.read(key: _claveAcceso);
  Future<String?> get refresco => _almacen.read(key: _claveRefresco);

  Future<void> guardar(String acceso, String? refresco) async {
    await _almacen.write(key: _claveAcceso, value: acceso);
    if (refresco != null) {
      await _almacen.write(key: _claveRefresco, value: refresco);
    }
  }

  Future<void> borrar() async {
    await _almacen.delete(key: _claveAcceso);
    await _almacen.delete(key: _claveRefresco);
    // La marca NO se borra al salir: es la identidad de la clínica, no
    // un dato del paciente, y conservarla hace que la pantalla de
    // ingreso siga siendo la de su clínica cuando vuelva a entrar. Se
    // reemplaza sola si ingresa con una cuenta de otra clínica.
  }

  Future<bool> get hayTokens async => (await acceso) != null;

  /// La marca guardada, si se llegó a pedir alguna vez.
  ///
  /// Sin esto, cada arranque en frío pinta medio segundo con los
  /// colores neutros y luego salta a los de la clínica. El parpadeo se
  /// ve, y se ve mal.
  Future<Marca?> get marca async {
    final crudo = await _almacen.read(key: _claveMarca);
    if (crudo == null) return null;
    try {
      return Marca.desdeJson(jsonDecode(crudo) as Map<String, dynamic>);
    } catch (_) {
      // Guardado por una versión anterior con otra forma: se descarta y
      // se vuelve a pedir. Mejor los colores neutros un momento que una
      // excepción al arrancar.
      return null;
    }
  }

  Future<void> guardarMarca(Marca marca) =>
      _almacen.write(key: _claveMarca, value: jsonEncode(marca.aJson()));
}

/// Mensaje legible de una respuesta de error.
///
/// La API envuelve sus errores en `{"error": {"message", "details"}}` y
/// DRF usa `{"detail": ...}`; se miran los dos antes de rendirse a un
/// «error 500» que no le dice nada a nadie.
String mensajeDeError(int codigo, String cuerpo) {
  if (codigo == 429) {
    return 'Demasiados intentos seguidos. Espera un momento y vuelve a probar.';
  }
  try {
    final Object? datos = jsonDecode(cuerpo);
    if (datos is Map<String, dynamic>) {
      final Object? sobre = datos['error'];
      if (sobre is Map<String, dynamic>) {
        final Object? detalles = sobre['details'];
        if (detalles is Map<String, dynamic> && detalles.isNotEmpty) {
          final Object? primero = detalles.values.first;
          if (primero is List && primero.isNotEmpty) return '${primero.first}';
          if (primero is String && primero.isNotEmpty) return primero;
        }
        final Object? mensaje = sobre['message'];
        if (mensaje is String && mensaje.isNotEmpty) return mensaje;
      }
      final Object? detalle = datos['detail'];
      if (detalle is String && detalle.isNotEmpty) return detalle;
    }
  } on FormatException {
    // Un cuerpo que no es JSON (una página de error de nginx, por
    // ejemplo) no debe tumbar la app: se cae al mensaje genérico.
  }
  return 'No se pudo completar la operación (error $codigo).';
}

class ClienteApi {
  ClienteApi({
    required this.urlBase,
    Sesion? sesion,
    http.Client? http_,
  })  : sesion = sesion ?? Sesion(),
        _http = http_ ?? http.Client();

  final String urlBase;
  final Sesion sesion;
  final http.Client _http;

  /// El refresco en vuelo, si lo hay. Ver la nota de arriba.
  Future<bool>? _refrescoEnVuelo;

  Uri _uri(String ruta) => Uri.parse('$urlBase/api/v1$ruta');

  // ── Entrada por OTP ──────────────────────────────────────────────

  /// Pide el código que llega por WhatsApp.
  Future<void> pedirCodigo(String telefono) async {
    final r = await _http.post(
      _uri('/auth/otp/request/'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'phone': telefono}),
    );
    if (r.statusCode >= 400) {
      throw ErrorDeApi(mensajeDeError(r.statusCode, r.body), codigo: r.statusCode);
    }
  }

  /// Canjea el código por los tokens y los deja guardados.
  Future<void> verificarCodigo(String telefono, String codigo) async {
    final r = await _http.post(
      _uri('/auth/otp/verify/'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'phone': telefono, 'code': codigo}),
    );
    if (r.statusCode >= 400) {
      throw ErrorDeApi(mensajeDeError(r.statusCode, r.body), codigo: r.statusCode);
    }
    final datos = jsonDecode(r.body) as Map<String, dynamic>;
    await sesion.guardar(datos['access'] as String, datos['refresh'] as String?);
  }

  Future<void> salir() => sesion.borrar();

  /// La marca de la clínica del paciente, guardada de paso.
  Future<Marca> marcaDeLaClinica() async {
    final marca = Marca.desdeJson(await objeto('/app/clinica/'));
    await sesion.guardarMarca(marca);
    return marca;
  }

  // ── Peticiones autenticadas ──────────────────────────────────────

  Future<Map<String, dynamic>> objeto(String ruta) async =>
      await _pedir(ruta) as Map<String, dynamic>;

  Future<List<dynamic>> lista(String ruta) async =>
      await _pedir(ruta) as List<dynamic>;

  Future<Object?> _pedir(String ruta) async {
    var r = await _get(ruta);
    if (r.statusCode == 401 && await _refrescar()) {
      r = await _get(ruta);
    }
    if (r.statusCode >= 400) {
      if (r.statusCode == 401) await sesion.borrar();
      throw ErrorDeApi(mensajeDeError(r.statusCode, r.body), codigo: r.statusCode);
    }
    return jsonDecode(r.body);
  }

  Future<http.Response> _get(String ruta) async {
    final token = await sesion.acceso;
    return _http.get(_uri(ruta), headers: {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    });
  }

  /// Un solo refresco a la vez, compartido por todas las peticiones que
  /// hayan chocado con el mismo 401.
  Future<bool> _refrescar() {
    return _refrescoEnVuelo ??= _refrescarDeVerdad().whenComplete(() {
      _refrescoEnVuelo = null;
    });
  }

  Future<bool> _refrescarDeVerdad() async {
    final token = await sesion.refresco;
    if (token == null) return false;
    final r = await _http.post(
      _uri('/auth/token/refresh/'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': token}),
    );
    if (r.statusCode >= 400) {
      await sesion.borrar();
      return false;
    }
    final datos = jsonDecode(r.body) as Map<String, dynamic>;
    await sesion.guardar(datos['access'] as String, datos['refresh'] as String?);
    return true;
  }
}
