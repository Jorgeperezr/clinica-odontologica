/// Los logros, con la dinámica de las «stories».
///
/// La fila de círculos de arriba no es decoración copiada: es la forma
/// más compacta que existe de enseñar «esto tienes y esto te falta» sin
/// ocupar media pantalla, y el paciente ya sabe usarla sin que nadie se
/// lo explique. El anillo de color significa ganado; el gris, por ganar.
///
/// Lo que NO se copia de Instagram: aquí no hay nada efímero ni ningún
/// contador de likes. Un logro clínico no caduca en 24 horas.
library;

import 'package:flutter/material.dart';

import '../api/formato.dart';
import '../api/modelos.dart';
import '../tema.dart';

/// Fila horizontal de logros, al estilo de las historias.
class FilaDeLogros extends StatelessWidget {
  const FilaDeLogros({super.key, required this.logros});

  final List<Logro> logros;

  @override
  Widget build(BuildContext context) {
    if (logros.isEmpty) return const _SinLogrosTodavia();
    return SizedBox(
      height: 112,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: logros.length,
        separatorBuilder: (_, __) => const SizedBox(width: 14),
        itemBuilder: (context, i) => _Burbuja(logro: logros[i]),
      ),
    );
  }
}

class _Burbuja extends StatelessWidget {
  const _Burbuja({required this.logro});

  final Logro logro;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return GestureDetector(
      onTap: () => mostrarLogro(context, logro),
      child: SizedBox(
        width: 76,
        child: Column(
          children: [
            Stack(
              alignment: Alignment.bottomRight,
              children: [
                _Anillo(
                  degradado: logro.esRacha ? anilloRacha : anilloLogro,
                  child: Icon(iconoDeLogro(logro.icono),
                      size: 28, color: tema.colorScheme.onSurface),
                ),
                if (logro.esRacha)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      gradient: anilloRacha,
                      borderRadius: BorderRadius.circular(99),
                      border: Border.all(color: tema.colorScheme.surface, width: 2),
                    ),
                    child: Text('${logro.racha}',
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w700)),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              logro.nombre,
              maxLines: 2,
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
              style: tema.textTheme.labelSmall,
            ),
          ],
        ),
      ),
    );
  }
}

/// El anillo de degradado: un círculo pintado detrás, con un hueco del
/// color del fondo para que se vea como aro y no como disco.
class _Anillo extends StatelessWidget {
  const _Anillo({required this.degradado, required this.child, this.apagado = false});

  final Gradient degradado;
  final Widget child;
  final bool apagado;

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Container(
      width: 70,
      height: 70,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: apagado ? null : degradado,
        color: apagado ? tema.dividerColor : null,
      ),
      child: Container(
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: tema.colorScheme.surface,
        ),
        child: Container(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: tema.colorScheme.surfaceContainerHighest,
          ),
          child: Center(child: child),
        ),
      ),
    );
  }
}

class _SinLogrosTodavia extends StatelessWidget {
  const _SinLogrosTodavia();

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Row(
        children: [
          const _Anillo(
            degradado: anilloLogro,
            apagado: true,
            child: Icon(Icons.star_outline, size: 26),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Todavía sin logros', style: tema.textTheme.titleSmall),
                const SizedBox(height: 2),
                Text(
                  'Acude a tus controles y sigue las indicaciones de tu '
                  'odontólogo para ganar el primero.',
                  style: tema.textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Detalle de un logro, en una hoja que sube desde abajo.
void mostrarLogro(BuildContext context, Logro logro) {
  showModalBottomSheet<void>(
    context: context,
    showDragHandle: true,
    builder: (context) {
      final tema = Theme.of(context);
      // Con scroll y no un Column suelto: un logro con descripción
      // larga, beneficio y contador de veces desborda la hoja en una
      // pantalla baja, y eso se ve como las rayas amarillas y negras.
      // Lo cazó la prueba de interfaz al tocar un logro.
      return SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(24, 0, 24, 36),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _Anillo(
                  degradado: logro.esRacha ? anilloRacha : anilloLogro,
                  child: Icon(iconoDeLogro(logro.icono), size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(logro.nombre, style: tema.textTheme.titleLarge),
                      Text(
                        logro.esRacha
                            ? '${logro.racha} meses seguidos'
                            : 'Obtenido el ${fechaLarga(logro.obtenido)}',
                        style: tema.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            if (logro.descripcion.isNotEmpty) ...[
              const SizedBox(height: 18),
              Text(logro.descripcion, style: tema.textTheme.bodyMedium),
            ],
            if (logro.tieneBeneficio) ...[
              const SizedBox(height: 18),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: tema.colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      const Icon(Icons.card_giftcard_outlined, size: 18),
                      const SizedBox(width: 8),
                      Text('Tu beneficio', style: tema.textTheme.titleSmall),
                    ]),
                    const SizedBox(height: 8),
                    Text(logro.beneficio, style: tema.textTheme.bodyMedium),
                    const SizedBox(height: 10),
                    // Se dice dónde se cobra el premio a propósito: el
                    // descuento NO se aplica solo, lo aplica la clínica
                    // al presupuestar. Prometer en la app algo que la
                    // recepción no sabe que existe es peor que no
                    // prometer nada.
                    Text(
                      'Recuérdaselo a tu clínica en tu próxima visita.',
                      style: tema.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
            if (logro.veces > 1) ...[
              const SizedBox(height: 14),
              Text('Lo has ganado ${logro.veces} veces.',
                  style: tema.textTheme.bodySmall),
            ],
          ],
        ),
      );
    },
  );
}
