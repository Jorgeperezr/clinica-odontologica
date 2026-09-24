/// Pedir cita y escribir a la clínica.
///
/// Las dos cosas llegan a la «Bandeja de la app» del panel, donde la
/// recepción agenda la cita (o explica por qué no puede) y contesta los
/// mensajes. Aquí el paciente ve en qué quedó cada cosa.
///
/// Sin dependencias nuevas: el día se elige en una tira con los próximos
/// días en castellano, en vez del calendario del sistema, que sin
/// `flutter_localizations` saldría en inglés.
library;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api/cliente.dart';
import '../api/formato.dart';
import '../api/modelos.dart';

class PantallaConsultorio extends StatelessWidget {
  const PantallaConsultorio(
      {super.key, required this.api, this.pestanaInicial = 0});

  final ClienteApi api;
  final int pestanaInicial;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      initialIndex: pestanaInicial,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Tu clínica'),
          bottom: const TabBar(tabs: [
            Tab(icon: Icon(Icons.event_available_outlined), text: 'Pedir cita'),
            Tab(icon: Icon(Icons.chat_bubble_outline), text: 'Mensajes'),
          ]),
        ),
        body: TabBarView(children: [
          _PedirCita(api: api),
          _Mensajes(api: api),
        ]),
      ),
    );
  }
}

void _aviso(BuildContext context, String texto) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(texto)));
}

// ── Pedir cita ─────────────────────────────────────────────────────────

class _PedirCita extends StatefulWidget {
  const _PedirCita({required this.api});

  final ClienteApi api;

  @override
  State<_PedirCita> createState() => _PedirCitaState();
}

class _PedirCitaState extends State<_PedirCita> {
  static const _diasVisibles = 60;
  static const _franjas = {
    'manana': 'Mañana',
    'tarde': 'Tarde',
    'cualquiera': 'Cualquier hora'
  };

  late DateTime _dia;
  String _franja = 'cualquiera';
  final _motivo = TextEditingController();
  bool _enviando = false;
  late Future<List<SolicitudCita>> _lista;

  @override
  void initState() {
    super.initState();
    final hoy = DateTime.now();
    _dia = DateTime(hoy.year, hoy.month, hoy.day).add(const Duration(days: 1));
    _lista = _cargar();
  }

  @override
  void dispose() {
    _motivo.dispose();
    super.dispose();
  }

  Future<List<SolicitudCita>> _cargar() async =>
      (await widget.api.lista('/app/solicitudes-cita/'))
          .map((e) => SolicitudCita.desdeJson(e as Map<String, dynamic>))
          .toList();

  Future<void> _enviar() async {
    setState(() => _enviando = true);
    try {
      await widget.api.enviar('/app/solicitudes-cita/', {
        'fecha_preferida': DateFormat('yyyy-MM-dd').format(_dia),
        'franja': _franja,
        'motivo': _motivo.text.trim(),
      });
      _motivo.clear();
      if (!mounted) return;
      // OJO: `setState(() => _lista = _cargar())` devuelve el Future de la
      // asignación y Flutter lo rechaza; el error caía en el `catch` y el
      // paciente veía «No hay conexión» con la cita YA pedida. Siempre con
      // llaves.
      _aviso(context, 'Listo. La clínica te confirmará la hora aquí mismo.');
      setState(() {
        _lista = _cargar();
      });
    } on ErrorDeApi catch (e) {
      if (mounted) _aviso(context, e.mensaje);
    } catch (_) {
      if (mounted) _aviso(context, 'No hay conexión. Inténtalo de nuevo.');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final hoy = DateTime.now();
    final inicio = DateTime(hoy.year, hoy.month, hoy.day);
    final dias =
        List.generate(_diasVisibles, (i) => inicio.add(Duration(days: i)));
    final estilo = Theme.of(context).textTheme;

    return RefreshIndicator(
      onRefresh: () async {
        setState(() {
          _lista = _cargar();
        });
        await _lista;
      },
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('¿Qué día te viene bien?', style: estilo.titleMedium),
          const SizedBox(height: 8),
          SizedBox(
            height: 64,
            child: ListView.separated(
              key: const Key('tira-de-dias'),
              scrollDirection: Axis.horizontal,
              itemCount: dias.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (context, i) {
                final d = dias[i];
                final elegido = d == _dia;
                return ChoiceChip(
                  selected: elegido,
                  onSelected: (_) => setState(() => _dia = d),
                  label: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text(DateFormat('EEE', 'es').format(d)),
                    Text(DateFormat('d MMM', 'es').format(d),
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                  ]),
                );
              },
            ),
          ),
          const SizedBox(height: 16),
          Text('¿A qué hora, más o menos?', style: estilo.titleMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            children: _franjas.entries
                .map((f) => ChoiceChip(
                      label: Text(f.value),
                      selected: _franja == f.key,
                      onSelected: (_) => setState(() => _franja = f.key),
                    ))
                .toList(),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _motivo,
            maxLength: 300,
            maxLines: 2,
            decoration: const InputDecoration(
              labelText: 'Motivo (opcional)',
              hintText: 'Ej.: me duele una muela, limpieza, control',
              border: OutlineInputBorder(),
            ),
          ),
          FilledButton.icon(
            onPressed: _enviando ? null : _enviar,
            icon: const Icon(Icons.send_outlined),
            label: Text(_enviando
                ? 'Enviando…'
                : 'Pedir cita para el ${fechaLarga(_dia)}'),
          ),
          const SizedBox(height: 8),
          Text('No es una cita todavía: la recepción te propone la hora.',
              style: estilo.bodySmall),
          const Divider(height: 32),
          Text('Tus solicitudes', style: estilo.titleMedium),
          const SizedBox(height: 8),
          FutureBuilder<List<SolicitudCita>>(
            future: _lista,
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Padding(
                  padding: EdgeInsets.all(16),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              if (snap.hasError) {
                final e = snap.error;
                return Text(e is ErrorDeApi
                    ? e.mensaje
                    : 'No se pudieron cargar tus solicitudes.');
              }
              final lista = snap.data ?? const [];
              if (lista.isEmpty) {
                return const Text(
                    'Aún no has pedido ninguna cita desde la app.');
              }
              return Column(
                  children: lista.map((s) => _TarjetaSolicitud(s: s)).toList());
            },
          ),
        ],
      ),
    );
  }
}

class _TarjetaSolicitud extends StatelessWidget {
  const _TarjetaSolicitud({required this.s});

  final SolicitudCita s;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final (Color fondo, IconData icono) = switch (s.estado) {
      'agendada' => (esquema.primaryContainer, Icons.check_circle_outline),
      'rechazada' => (esquema.errorContainer, Icons.info_outline),
      _ => (esquema.surfaceContainerHighest, Icons.schedule),
    };
    return Card(
      child: ListTile(
        leading: Icon(icono),
        title: Text(s.citaInicio != null
            ? 'Cita: ${fechaYHora(s.citaInicio!)}'
            : '${fechaLarga(s.fechaPreferida)} · ${s.franjaTexto.toLowerCase()}'),
        subtitle:
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (s.motivo.isNotEmpty) Text('«${s.motivo}»'),
          if (s.respuesta.isNotEmpty)
            Text('La clínica: ${s.respuesta}',
                style: const TextStyle(fontWeight: FontWeight.w600)),
        ]),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
              color: fondo, borderRadius: BorderRadius.circular(12)),
          child: Text(s.estadoTexto, style: const TextStyle(fontSize: 12)),
        ),
      ),
    );
  }
}

// ── Mensajes ───────────────────────────────────────────────────────────

class _Mensajes extends StatefulWidget {
  const _Mensajes({required this.api});

  final ClienteApi api;

  @override
  State<_Mensajes> createState() => _MensajesState();
}

class _MensajesState extends State<_Mensajes> {
  final _texto = TextEditingController();
  bool _enviando = false;
  late Future<List<MensajeConsultorio>> _lista;

  @override
  void initState() {
    super.initState();
    _lista = _cargar();
  }

  @override
  void dispose() {
    _texto.dispose();
    super.dispose();
  }

  Future<List<MensajeConsultorio>> _cargar() async =>
      (await widget.api.lista('/app/mensajes/'))
          .map((e) => MensajeConsultorio.desdeJson(e as Map<String, dynamic>))
          .toList();

  Future<void> _enviar() async {
    final texto = _texto.text.trim();
    if (texto.isEmpty) return;
    setState(() => _enviando = true);
    try {
      await widget.api.enviar('/app/mensajes/', {'texto': texto});
      _texto.clear();
      if (!mounted) return;
      setState(() {
        _lista = _cargar();
      });
    } on ErrorDeApi catch (e) {
      if (mounted) _aviso(context, e.mensaje);
    } catch (_) {
      if (mounted) _aviso(context, 'No hay conexión. Tu mensaje no se envió.');
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Expanded(
        child: RefreshIndicator(
          onRefresh: () async {
            setState(() {
              _lista = _cargar();
            });
            await _lista;
          },
          child: FutureBuilder<List<MensajeConsultorio>>(
            future: _lista,
            builder: (context, snap) {
              if (snap.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snap.hasError) {
                final e = snap.error;
                return ListView(padding: const EdgeInsets.all(24), children: [
                  Text(e is ErrorDeApi
                      ? e.mensaje
                      : 'No se pudieron cargar tus mensajes.'),
                ]);
              }
              final lista = snap.data ?? const [];
              if (lista.isEmpty) {
                return ListView(
                    padding: const EdgeInsets.all(24),
                    children: const [
                      Text(
                          '¿Tienes una duda? Escríbela abajo y la clínica te contestará aquí.'),
                    ]);
              }
              // La API da lo más reciente primero; como en un chat, se
              // pinta al revés para que lo último quede abajo.
              return ListView(
                reverse: true,
                padding: const EdgeInsets.all(12),
                children: lista.map((m) => _Hilo(m: m)).toList(),
              );
            },
          ),
        ),
      ),
      SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 8, 8),
          child: Row(children: [
            Expanded(
              child: TextField(
                controller: _texto,
                minLines: 1,
                maxLines: 4,
                maxLength: 1000,
                decoration: const InputDecoration(
                  hintText: 'Escribe a la clínica…',
                  counterText: '',
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            IconButton.filled(
              tooltip: 'Enviar',
              onPressed: _enviando ? null : _enviar,
              icon: const Icon(Icons.send),
            ),
          ]),
        ),
      ),
    ]);
  }
}

class _Hilo extends StatelessWidget {
  const _Hilo({required this.m});

  final MensajeConsultorio m;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    final estilo = Theme.of(context).textTheme;
    Widget burbuja(String texto, String pie, {required bool mio}) => Align(
          alignment: mio ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            constraints: const BoxConstraints(maxWidth: 320),
            margin: const EdgeInsets.symmetric(vertical: 4),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: mio
                  ? esquema.primaryContainer
                  : esquema.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(14),
            ),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(texto),
              const SizedBox(height: 4),
              Text(pie, style: estilo.bodySmall),
            ]),
          ),
        );
    return Column(children: [
      burbuja(m.texto, fechaYHora(m.creado), mio: true),
      if (m.tieneRespuesta)
        burbuja(m.respuesta, 'La clínica · ${fechaYHora(m.respondido!)}',
            mio: false)
      else
        Align(
          alignment: Alignment.centerRight,
          child: Text('Esperando respuesta', style: estilo.bodySmall),
        ),
    ]);
  }
}
