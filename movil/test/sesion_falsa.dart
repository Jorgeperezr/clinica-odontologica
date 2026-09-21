/// Sesión en memoria para las pruebas.
///
/// `flutter_secure_storage` necesita Keychain o Keystore, que en una
/// prueba de escritorio no existen.
library;

import 'package:clinica_paciente/api/cliente.dart';

class SesionFalsa implements Sesion {
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
