/// Entrada del paciente: teléfono y código por WhatsApp.
///
/// No hay contraseña a propósito. Un paciente entra en su app dos veces
/// al año, y una contraseña que se usa dos veces al año es una
/// contraseña olvidada o apuntada en un papel.
library;

import 'package:flutter/material.dart';

import '../api/cliente.dart';
import '../api/modelos.dart';

class PantallaIngreso extends StatefulWidget {
  const PantallaIngreso({
    super.key,
    required this.api,
    required this.alEntrar,
    this.marca = Marca.neutra,
  });

  final ClienteApi api;
  final VoidCallback alEntrar;

  /// La de la última clínica con la que se ingresó, si la hay. En el
  /// primer arranque del teléfono no se sabe de qué clínica se trata
  /// —no hay sesión— y se usa la neutra.
  final Marca marca;

  @override
  State<PantallaIngreso> createState() => _PantallaIngresoState();
}

class _PantallaIngresoState extends State<PantallaIngreso> {
  final _telefono = TextEditingController();
  final _codigo = TextEditingController();
  bool _codigoPedido = false;
  bool _ocupado = false;
  String? _error;

  @override
  void dispose() {
    _telefono.dispose();
    _codigo.dispose();
    super.dispose();
  }

  Future<void> _ejecutar(Future<void> Function() accion) async {
    setState(() {
      _ocupado = true;
      _error = null;
    });
    try {
      await accion();
    } on ErrorDeApi catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'No se pudo contactar con la clínica. '
            'Revisa tu conexión e inténtalo otra vez.');
      }
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _pedir() => _ejecutar(() async {
        await widget.api.pedirCodigo(_telefono.text.trim());
        if (mounted) setState(() => _codigoPedido = true);
      });

  Future<void> _verificar() => _ejecutar(() async {
        await widget.api.verificarCodigo(_telefono.text.trim(), _codigo.text.trim());
        widget.alEntrar();
      });

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _Emblema(marca: widget.marca, color: tema.colorScheme.primary),
                  const SizedBox(height: 20),
                  Text(widget.marca.nombre, style: tema.textTheme.headlineMedium),
                  const SizedBox(height: 6),
                  Text(
                    _codigoPedido
                        ? 'Te enviamos un código por WhatsApp al $_telefonoVisible.'
                        : 'Ingresa con tu número de teléfono. Te enviaremos un '
                            'código por WhatsApp.',
                    style: tema.textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 22),
                  if (_error != null) ...[
                    _Aviso(texto: _error!),
                    const SizedBox(height: 14),
                  ],
                  TextField(
                    controller: _telefono,
                    enabled: !_codigoPedido && !_ocupado,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Teléfono',
                      hintText: '+593 99 911 1222',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (_codigoPedido) ...[
                    const SizedBox(height: 14),
                    TextField(
                      controller: _codigo,
                      enabled: !_ocupado,
                      keyboardType: TextInputType.number,
                      autofocus: true,
                      decoration: const InputDecoration(
                        labelText: 'Código de 6 dígitos',
                        border: OutlineInputBorder(),
                      ),
                      onSubmitted: (_) => _verificar(),
                    ),
                  ],
                  const SizedBox(height: 18),
                  FilledButton(
                    onPressed: _ocupado ? null : (_codigoPedido ? _verificar : _pedir),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Text(_ocupado
                          ? 'Un momento…'
                          : (_codigoPedido ? 'Entrar' : 'Enviarme el código')),
                    ),
                  ),
                  if (_codigoPedido)
                    TextButton(
                      onPressed: _ocupado
                          ? null
                          : () => setState(() {
                                _codigoPedido = false;
                                _codigo.clear();
                              }),
                      child: const Text('Usar otro número'),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  String get _telefonoVisible {
    final t = _telefono.text.trim();
    // No se repite el número entero: si alguien mira por encima del
    // hombro, los últimos dígitos bastan para reconocerlo.
    return t.length > 4 ? '••• ${t.substring(t.length - 4)}' : t;
  }
}

class _Aviso extends StatelessWidget {
  const _Aviso({required this.texto});

  final String texto;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: tema.colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(texto, style: TextStyle(color: tema.colorScheme.onErrorContainer)),
    );
  }
}


/// El logotipo de la clínica, o el icono genérico si no tiene.
///
/// `errorBuilder` no es opcional: el logotipo se carga desde la red y un
/// servidor caído, una URL vieja o un archivo borrado dejarían un aspa
/// rota presidiendo la pantalla de ingreso. Se cae al icono, que nunca
/// falla.
class _Emblema extends StatelessWidget {
  const _Emblema({required this.marca, required this.color});

  final Marca marca;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (!marca.tieneLogo) {
      return Icon(Icons.medical_services_outlined, size: 64, color: color);
    }
    return Image.network(
      marca.logo!,
      height: 72,
      fit: BoxFit.contain,
      errorBuilder: (context, _, __) =>
          Icon(Icons.medical_services_outlined, size: 64, color: color),
    );
  }
}
