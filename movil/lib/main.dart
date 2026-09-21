/// Aplicación del paciente.
///
/// Consume `apps/app_paciente` de la API (Sprint 89): sus citas, lo que
/// debe y las indicaciones que su profesional marcó como visibles. Nada
/// más: ni odontograma, ni notas clínicas, ni costes internos.
library;

import 'package:flutter/material.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'api/cliente.dart';
import 'pantallas/ingreso.dart';
import 'pantallas/principal.dart';

/// Dónde vive la API.
///
/// Se pasa al compilar y no se escribe aquí a fuego:
///
///     flutter build apk --dart-define=API_URL=https://clinica.ejemplo.ec
///
/// El valor por omisión es el del emulador de Android, donde `10.0.2.2`
/// es la máquina que lo hospeda. En un iPhone o en un dispositivo real
/// hay que pasar la URL de verdad.
const urlApi = String.fromEnvironment(
  'API_URL',
  defaultValue: 'http://10.0.2.2',
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
  late Future<bool> _haySesion;

  @override
  void initState() {
    super.initState();
    _haySesion = _api.sesion.hayTokens;
  }

  void _refrescarSesion() => setState(() {
        _haySesion = _api.sesion.hayTokens;
      });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mi clínica',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF14607A),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorSchemeSeed: const Color(0xFF14607A),
        brightness: Brightness.dark,
        useMaterial3: true,
      ),
      home: FutureBuilder<bool>(
        future: _haySesion,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          if (snap.data ?? false) {
            return PantallaPrincipal(api: _api, alSalir: _refrescarSesion);
          }
          return PantallaIngreso(api: _api, alEntrar: _refrescarSesion);
        },
      ),
    );
  }
}
