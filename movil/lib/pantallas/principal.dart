/// Las cuatro pantallas de dentro: inicio, citas, cuenta e indicaciones.
///
/// Un patrón repetido en las cuatro, y es el que evita la pantalla en
/// blanco: cada una tiene TRES estados —cargando, error y contenido— y
/// el error se enseña con su motivo y un botón de reintentar. Una app
/// médica que se queda en blanco cuando falla la red hace que el
/// paciente crea que no tiene ninguna cita.
library;

import 'package:flutter/material.dart';

import '../api/cliente.dart';
import '../api/formato.dart';
import '../api/modelos.dart';

class PantallaPrincipal extends StatefulWidget {
  const PantallaPrincipal({super.key, required this.api, required this.alSalir});

  final ClienteApi api;
  final VoidCallback alSalir;

  @override
  State<PantallaPrincipal> createState() => _PantallaPrincipalState();
}

class _PantallaPrincipalState extends State<PantallaPrincipal> {
  int _indice = 0;

  @override
  Widget build(BuildContext context) {
    final paginas = [
      _Inicio(api: widget.api),
      _Citas(api: widget.api),
      _Cuenta(api: widget.api),
      _Indicaciones(api: widget.api),
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi clínica'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Salir',
            onPressed: () async {
              await widget.api.salir();
              widget.alSalir();
            },
          ),
        ],
      ),
      body: paginas[_indice],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _indice,
        onDestinationSelected: (i) => setState(() => _indice = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Inicio'),
          NavigationDestination(icon: Icon(Icons.event_outlined), label: 'Citas'),
          NavigationDestination(icon: Icon(Icons.receipt_long_outlined), label: 'Cuenta'),
          NavigationDestination(icon: Icon(Icons.healing_outlined), label: 'Cuidados'),
        ],
      ),
    );
  }
}

/// Envoltorio con los tres estados. Todo lo que se pide a la API pasa
/// por aquí, así que ninguna pantalla puede olvidarse de tratar el error.
class _Cargador<T> extends StatefulWidget {
  const _Cargador({required this.pedir, required this.construir, super.key});

  final Future<T> Function() pedir;
  final Widget Function(BuildContext, T) construir;

  @override
  State<_Cargador<T>> createState() => _CargadorState<T>();
}

class _CargadorState<T> extends State<_Cargador<T>> {
  late Future<T> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = widget.pedir();
  }

  void _reintentar() => setState(() => _futuro = widget.pedir());

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: _futuro,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          final e = snap.error;
          return _PantallaError(
            mensaje: e is ErrorDeApi
                ? e.mensaje
                : 'No se pudo contactar con la clínica. Revisa tu conexión.',
            alReintentar: _reintentar,
          );
        }
        return RefreshIndicator(
          onRefresh: () async => _reintentar(),
          child: widget.construir(context, snap.data as T),
        );
      },
    );
  }
}

class _PantallaError extends StatelessWidget {
  const _PantallaError({required this.mensaje, required this.alReintentar});

  final String mensaje;
  final VoidCallback alReintentar;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_outlined, size: 52),
            const SizedBox(height: 14),
            Text(mensaje, textAlign: TextAlign.center),
            const SizedBox(height: 18),
            FilledButton.tonal(
              onPressed: alReintentar,
              child: const Text('Reintentar'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Vacio extends StatelessWidget {
  const _Vacio({required this.icono, required this.texto});

  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) {
    // Lista y no Column: hace falta que se pueda arrastrar para que el
    // «tirar para recargar» funcione también cuando no hay nada.
    return ListView(
      padding: const EdgeInsets.all(40),
      children: [
        Icon(icono, size: 52, color: Theme.of(context).disabledColor),
        const SizedBox(height: 14),
        Text(texto, textAlign: TextAlign.center),
      ],
    );
  }
}

/* ── Inicio ────────────────────────────────────────────────────────── */

class _Inicio extends StatelessWidget {
  const _Inicio({required this.api});

  final ClienteApi api;

  @override
  Widget build(BuildContext context) {
    return _Cargador<Perfil>(
      pedir: () async => Perfil.desdeJson(await api.objeto('/app/me/')),
      construir: (context, p) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Hola, ${p.nombre.split(' ').first}',
              style: Theme.of(context).textTheme.headlineSmall),
          Text(p.clinica, style: Theme.of(context).textTheme.bodyMedium),
          const SizedBox(height: 18),
          if (p.proximaCita != null)
            _Tarjeta(
              icono: Icons.event_available_outlined,
              titulo: 'Tu próxima cita',
              lineas: [
                '${fechaYHora(p.proximaCita!.inicio)} · ${cuandoEs(p.proximaCita!.inicio)}',
                if (p.proximaCita!.motivo != null) p.proximaCita!.motivo!,
                if (p.proximaCita!.doctor != null) 'Con ${p.proximaCita!.doctor}',
              ],
            )
          else
            const _Tarjeta(
              icono: Icons.event_busy_outlined,
              titulo: 'Sin citas agendadas',
              lineas: ['Llama a tu clínica para reservar una.'],
            ),
          const SizedBox(height: 12),
          _Tarjeta(
            icono: p.estaEnMora
                ? Icons.warning_amber_outlined
                : Icons.account_balance_wallet_outlined,
            titulo: p.tieneDeuda ? 'Saldo pendiente: ${dinero(p.saldo)}' : 'Estás al día',
            alerta: p.estaEnMora,
            lineas: [
              if (p.estaEnMora)
                '${p.cuotasVencidas} '
                    '${p.cuotasVencidas == 1 ? "cuota vencida" : "cuotas vencidas"}'
              else if (p.tieneDeuda)
                '${p.cuotasPendientes} '
                    '${p.cuotasPendientes == 1 ? "cuota por vencer" : "cuotas por vencer"}'
              else
                'No tienes cuotas pendientes.',
            ],
          ),
          if (p.convenio != null) ...[
            const SizedBox(height: 12),
            _Tarjeta(
              icono: Icons.badge_outlined,
              titulo: 'Convenio',
              lineas: [p.convenio!],
            ),
          ],
        ],
      ),
    );
  }
}

class _Tarjeta extends StatelessWidget {
  const _Tarjeta({
    required this.icono,
    required this.titulo,
    required this.lineas,
    this.alerta = false,
  });

  final IconData icono;
  final String titulo;
  final List<String> lineas;
  final bool alerta;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Card(
      color: alerta ? tema.colorScheme.errorContainer : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icono, size: 30),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(titulo, style: tema.textTheme.titleMedium),
                  const SizedBox(height: 4),
                  for (final l in lineas)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(l, style: tema.textTheme.bodyMedium),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/* ── Citas ─────────────────────────────────────────────────────────── */

class _Citas extends StatelessWidget {
  const _Citas({required this.api});

  final ClienteApi api;

  @override
  Widget build(BuildContext context) {
    return _Cargador<Agenda>(
      pedir: () async => Agenda.desdeJson(await api.objeto('/app/citas/')),
      construir: (context, a) {
        if (a.vacia) {
          return const _Vacio(
            icono: Icons.event_busy_outlined,
            texto: 'Todavía no tienes citas registradas.',
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (a.proximas.isNotEmpty) ...[
              const _Titulo('Próximas'),
              for (final c in a.proximas) _FilaCita(cita: c, proxima: true),
              const SizedBox(height: 18),
            ],
            if (a.anteriores.isNotEmpty) ...[
              const _Titulo('Anteriores'),
              for (final c in a.anteriores) _FilaCita(cita: c, proxima: false),
            ],
          ],
        );
      },
    );
  }
}

class _Titulo extends StatelessWidget {
  const _Titulo(this.texto);

  final String texto;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(texto, style: Theme.of(context).textTheme.titleMedium),
      );
}

class _FilaCita extends StatelessWidget {
  const _FilaCita({required this.cita, required this.proxima});

  final Cita cita;
  final bool proxima;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(proxima ? Icons.event_available_outlined : Icons.history),
        title: Text(fechaYHora(cita.inicio)),
        subtitle: Text([
          if (cita.motivo != null) cita.motivo!,
          if (cita.doctor != null) 'Con ${cita.doctor}',
          cita.estado,
        ].join(' · ')),
        trailing: proxima ? Text(cuandoEs(cita.inicio)) : null,
      ),
    );
  }
}

/* ── Cuenta ────────────────────────────────────────────────────────── */

class _Cuenta extends StatelessWidget {
  const _Cuenta({required this.api});

  final ClienteApi api;

  @override
  Widget build(BuildContext context) {
    return _Cargador<EstadoDeCuenta>(
      pedir: () async => EstadoDeCuenta.desdeJson(await api.objeto('/app/saldo/')),
      construir: (context, e) {
        if (e.cuotas.isEmpty) {
          return const _Vacio(
            icono: Icons.receipt_long_outlined,
            texto: 'No tienes cuotas registradas.',
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _Tarjeta(
              icono: e.alDia
                  ? Icons.check_circle_outline
                  : Icons.warning_amber_outlined,
              titulo: 'Saldo pendiente: ${dinero(e.saldoTotal)}',
              alerta: !e.alDia,
              lineas: [e.alDia ? 'Sin cuotas vencidas.' : 'Tienes cuotas vencidas.'],
            ),
            const SizedBox(height: 14),
            const _Titulo('Cuotas'),
            for (final c in e.cuotas) _FilaCuota(cuota: c),
          ],
        );
      },
    );
  }
}

class _FilaCuota extends StatelessWidget {
  const _FilaCuota({required this.cuota});

  final Cuota cuota;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Card(
      color: cuota.vencida ? tema.colorScheme.errorContainer : null,
      child: ListTile(
        leading: CircleAvatar(child: Text('${cuota.numero}')),
        title: Text('${dinero(cuota.monto)} · vence ${fechaLarga(cuota.vence)}'),
        subtitle: Text(cuota.vencida
            ? 'Vencida ${cuandoEs(cuota.vence)} · pendiente ${dinero(cuota.saldo)}'
            : '${cuota.estado} · pendiente ${dinero(cuota.saldo)}'),
      ),
    );
  }
}

/* ── Indicaciones ──────────────────────────────────────────────────── */

class _Indicaciones extends StatelessWidget {
  const _Indicaciones({required this.api});

  final ClienteApi api;

  @override
  Widget build(BuildContext context) {
    return _Cargador<List<Indicacion>>(
      pedir: () async => (await api.lista('/app/indicaciones/'))
          .map((e) => Indicacion.desdeJson(e as Map<String, dynamic>))
          .toList(),
      construir: (context, lista) {
        if (lista.isEmpty) {
          return const _Vacio(
            icono: Icons.healing_outlined,
            texto: 'Tu profesional no te ha dejado indicaciones todavía.',
          );
        }
        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: lista.length,
          itemBuilder: (context, i) {
            final ind = lista[i];
            return Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(ind.tipo.toLowerCase().contains('receta')
                            ? Icons.medication_outlined
                            : Icons.healing_outlined),
                        const SizedBox(width: 8),
                        Text(ind.tipo,
                            style: Theme.of(context).textTheme.titleSmall),
                        const Spacer(),
                        Text(fechaLarga(ind.fecha),
                            style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(ind.texto),
                    if (ind.profesional != null) ...[
                      const SizedBox(height: 8),
                      Text(ind.profesional!,
                          style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}
