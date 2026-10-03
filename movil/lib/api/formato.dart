/// Cómo se le enseñan al paciente fechas y dinero.
library;

import 'package:intl/intl.dart';

/// «mié 24 sept, 08:23». El paciente necesita saber cuándo tiene que
/// estar allí, no leer un ISO-8601.
String fechaYHora(DateTime d) => DateFormat("EEE d MMM, HH:mm", 'es').format(d);

/// «24 de septiembre de 2026», para fechas sueltas sin hora.
String fechaLarga(DateTime d) => DateFormat("d 'de' MMMM 'de' y", 'es').format(d);

/// «$120.00».
///
/// El importe llega como cadena desde la API —viene de un `Decimal`— y
/// aquí solo se le pone el símbolo delante. NO se convierte a `double`:
/// redondear dinero para pintarlo es como aparecen las facturas que no
/// cuadran por un centavo.
String dinero(String importe) {
  final limpio = importe.trim();
  return limpio.startsWith('\$') ? limpio : '\$$limpio';
}

/// Cuántos días faltan (o han pasado) respecto de hoy, en palabras.
String cuandoEs(DateTime fecha, {DateTime? hoy}) {
  final ahora = hoy ?? DateTime.now();
  final dias = DateTime(fecha.year, fecha.month, fecha.day)
      .difference(DateTime(ahora.year, ahora.month, ahora.day))
      .inDays;
  if (dias == 0) return 'hoy';
  if (dias == 1) return 'mañana';
  if (dias == -1) return 'ayer';
  if (dias > 1) return 'en $dias días';
  return 'hace ${-dias} días';
}
