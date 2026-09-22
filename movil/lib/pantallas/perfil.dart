/// El perfil: quién es el paciente y todo lo que ha ganado.
///
/// Es la pestaña que en Instagram lleva la rejilla de fotos; aquí lleva
/// la rejilla de logros, que es lo que esta app tiene que enseñar con
/// orgullo. Y es donde vive el botón de salir, que es donde lo busca
/// cualquiera que haya usado una app con pestañas.
library;

import 'package:flutter/material.dart';

import '../api/cliente.dart';
import '../api/modelos.dart';
import '../tema.dart';
import 'logros.dart';

class PantallaPerfil extends StatefulWidget {
  const PantallaPerfil({super.key, required this.api, required this.alSalir});

  final ClienteApi api;
  final VoidCallback alSalir;

  @override
  State<PantallaPerfil> createState() => _PantallaPerfilState();
}

class _PantallaPerfilState extends State<PantallaPerfil> {
  late Future<(Perfil, List<Logro>)> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = _cargar();
  }

  Future<(Perfil, List<Logro>)> _cargar() async {
    final r = await Future.wait([
      widget.api.objeto('/app/me/'),
      widget.api.lista('/app/logros/'),
    ]);
    return (
      Perfil.desdeJson(r[0] as Map<String, dynamic>),
      (r[1] as List<dynamic>)
          .map((e) => Logro.desdeJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<(Perfil, List<Logro>)>(
      future: _futuro,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          final e = snap.error;
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.cloud_off_outlined, size: 52),
                  const SizedBox(height: 14),
                  Text(
                    e is ErrorDeApi
                        ? e.mensaje
                        : 'No se pudo contactar con la clínica.',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 18),
                  FilledButton.tonal(
                    onPressed: () => setState(() => _futuro = _cargar()),
                    child: const Text('Reintentar'),
                  ),
                ],
              ),
            ),
          );
        }
        final (p, logros) = snap.data!;
        return RefreshIndicator(
          onRefresh: () async => setState(() => _futuro = _cargar()),
          child: _Contenido(
            perfil: p,
            logros: logros,
            alSalir: () async {
              await widget.api.salir();
              widget.alSalir();
            },
          ),
        );
      },
    );
  }
}

class _Contenido extends StatelessWidget {
  const _Contenido({
    required this.perfil,
    required this.logros,
    required this.alSalir,
  });

  final Perfil perfil;
  final List<Logro> logros;
  final Future<void> Function() alSalir;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final iniciales = perfil.nombre
        .trim()
        .split(RegExp(r'\s+'))
        .take(2)
        .map((t) => t.isEmpty ? '' : t[0].toUpperCase())
        .join();

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        Row(
          children: [
            Container(
              width: 84,
              height: 84,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: anilloLogro,
              ),
              child: Center(
                child: Text(iniciales,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.w700)),
              ),
            ),
            const SizedBox(width: 20),
            Expanded(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _Contador(valor: '${logros.length}', etiqueta: 'logros'),
                  _Contador(
                    valor: '${logros.fold<int>(0, (a, l) => a > l.racha ? a : l.racha)}',
                    etiqueta: 'mejor racha',
                  ),
                  _Contador(
                    valor: perfil.cuotasPendientes == 0 ? '✓' : '${perfil.cuotasPendientes}',
                    etiqueta: perfil.cuotasPendientes == 0 ? 'al día' : 'cuotas',
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 18),
        Text(perfil.nombre, style: tema.textTheme.titleMedium),
        Text(perfil.clinica, style: tema.textTheme.bodyMedium),
        if (perfil.cedula != null)
          Text('CI ${perfil.cedula}', style: tema.textTheme.bodySmall),
        if (perfil.convenio != null) ...[
          const SizedBox(height: 8),
          Chip(
            avatar: const Icon(Icons.badge_outlined, size: 16),
            label: Text(perfil.convenio!),
            visualDensity: VisualDensity.compact,
          ),
        ],
        const SizedBox(height: 22),
        const Divider(),
        const SizedBox(height: 14),
        Text('Tus logros', style: tema.textTheme.titleMedium),
        const SizedBox(height: 12),
        if (logros.isEmpty)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 28),
            child: Column(
              children: [
                Icon(Icons.emoji_events_outlined,
                    size: 48, color: tema.disabledColor),
                const SizedBox(height: 12),
                Text(
                  'Todavía no tienes logros.\nAcude a tus controles y sigue '
                  'las indicaciones de tu odontólogo.',
                  textAlign: TextAlign.center,
                  style: tema.textTheme.bodyMedium,
                ),
              ],
            ),
          )
        else
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              childAspectRatio: 0.85,
            ),
            itemCount: logros.length,
            itemBuilder: (context, i) => _Celda(logro: logros[i]),
          ),
        const SizedBox(height: 28),
        OutlinedButton.icon(
          onPressed: alSalir,
          icon: const Icon(Icons.logout),
          label: const Text('Cerrar sesión'),
        ),
      ],
    );
  }
}

class _Contador extends StatelessWidget {
  const _Contador({required this.valor, required this.etiqueta});

  final String valor;
  final String etiqueta;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Column(
      children: [
        Text(valor, style: tema.textTheme.titleLarge),
        Text(etiqueta, style: tema.textTheme.bodySmall),
      ],
    );
  }
}

class _Celda extends StatelessWidget {
  const _Celda({required this.logro});

  final Logro logro;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return InkWell(
      onTap: () => mostrarLogro(context, logro),
      borderRadius: BorderRadius.circular(14),
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: tema.colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ShaderMask(
              shaderCallback: (r) =>
                  (logro.esRacha ? anilloRacha : anilloLogro).createShader(r),
              child: Icon(iconoDeLogro(logro.icono), size: 32, color: Colors.white),
            ),
            const SizedBox(height: 8),
            Text(
              logro.nombre,
              maxLines: 2,
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
              style: tema.textTheme.labelSmall,
            ),
            if (logro.esRacha)
              Text('${logro.racha} meses', style: tema.textTheme.labelSmall),
          ],
        ),
      ),
    );
  }
}
