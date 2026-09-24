/// Aplicación del paciente.
///
/// Consume `apps/app_paciente` de la API (Sprint 89): sus citas, lo que
/// debe y las indicaciones que su profesional marcó como visibles. Nada
/// más: ni odontograma, ni notas clínicas, ni costes internos.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'api/cliente.dart';
import 'api/modelos.dart';
import 'pantallas/ingreso.dart';
import 'pantallas/principal.dart';
import 'tema.dart';

/// Dónde vive la API.
///
/// Se pasa al compilar y no se escribe aquí a fuego:
///
///     flutter build apk --dart-define=API_URL=https://clinica.ejemplo.ec
///
/// El valor por omisión es el del emulador de Android contra
/// `scripts/start-local.sh`, que levanta Django en el 8000: dentro del
/// emulador, `10.0.2.2` es la máquina que lo hospeda. El simulador de
/// iOS comparte la red del Mac y usa `http://localhost:8000`; un
/// teléfono de verdad necesita la IP del Mac en la wifi.
const urlApi = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Sin esto, `DateFormat` con 'es' lanza en cuanto se pinta la primera
  // fecha: los datos de localización no se cargan solos.
  await initializeDateFormatting('es');
  runApp(const AppPaciente());
}

class AppPaciente extends StatefulWidget {
  const AppPaciente({super.key});

  @override
  State<AppPaciente> createState() => _AppPacienteState();
}

class _AppPacienteState extends State<AppPaciente> {
  final _api = ClienteApi(urlBase: urlApi);
  late Future<_Arranque> _arranque;

  /// La marca con la que se está pintando ahora mismo. Empieza en la
  /// neutra y se sustituye en cuanto se sabe de qué clínica se trata.
  Marca _marca = Marca.neutra;

  @override
  void initState() {
    super.initState();
    _arranque = _preparar();
  }

  /// Se mira la marca GUARDADA antes de pintar nada.
  ///
  /// Si se pidiera al servidor, la app arrancaría con los colores
  /// neutros y saltaría a los de la clínica medio segundo después. Ese
  /// parpadeo se ve. Lo guardado se refresca luego, sin prisa.
  Future<_Arranque> _preparar() async {
    final guardada = await _api.sesion.marca;
    if (guardada != null) _marca = guardada;
    final hay = await _api.sesion.hayTokens;
    if (hay) unawaited(_refrescarMarca());
    return _Arranque(haySesion: hay, marca: _marca);
  }

  /// Vuelve a pedir la marca por si la clínica cambió de logotipo o de
  /// colores. Si falla, se sigue con la guardada: que no se pueda pedir
  /// el logotipo no es motivo para dejar al paciente sin sus citas.
  Future<void> _refrescarMarca() async {
    try {
      final fresca = await _api.marcaDeLaClinica();
      if (mounted) setState(() => _marca = fresca);
    } catch (_) {
      // Sin red, o la cuenta todavía sin ficha. Se conserva lo guardado.
    }
  }

  void _refrescarSesion() {
    setState(() => _arranque = _preparar());
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mi clínica',
      debugShowCheckedModeBanner: false,
      theme: temaClaro(_marca.colorPrincipal),
      darkTheme: temaOscuro(_marca.colorPrincipal),
      home: FutureBuilder<_Arranque>(
        future: _arranque,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          if (snap.data?.haySesion ?? false) {
            return PantallaPrincipal(
              api: _api, marca: _marca, alSalir: _refrescarSesion);
          }
          return PantallaIngreso(
            api: _api, marca: _marca, alEntrar: _refrescarSesion);
        },
      ),
    );
  }
}


/// Lo que hay que saber antes de pintar la primera pantalla.
class _Arranque {
  const _Arranque({required this.haySesion, required this.marca});

  final bool haySesion;
  final Marca marca;
}
