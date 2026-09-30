/// El aspecto de la app.
///
/// La dinámica es la de Instagram —una fila de círculos arriba, un muro
/// de tarjetas debajo, cinco pestañas al pie— pero los colores no: los
/// de la clínica, que por omisión son los de Clinube (cian sobre tinta).
///
/// Los degradados de los anillos tampoco son los de Instagram. Dicen
/// algo: el ámbar/coral es para las rachas vivas, el cian para un logro
/// suelto, y el gris para los que todavía no se han ganado.
///
/// «Sin color» —un ajuste de cada paciente, en su perfil, o el tema que
/// eligió su clínica— pasa todo a grises: el tema, los anillos y el
/// logotipo. No cambia nada más; las rachas y los logros se siguen
/// distinguiendo por lo claro u oscuro.
library;

import 'package:flutter/material.dart';

// La paleta de Clinube. La misma que `frontend/lib/marca.js`.
const tinta = Color(0xFF0B1220);
const cian = Color(0xFF0E7490);
const cianLuz = Color(0xFF67E8F9);
const ambar = Color(0xFFE0922F);
const coral = Color(0xFFE2603F);

/// Los degradados de los anillos, según haya color o no.
@immutable
class Anillos extends ThemeExtension<Anillos> {
  const Anillos({required this.racha, required this.logro});

  /// Anillo de una racha viva: llama.
  final LinearGradient racha;

  /// Anillo de un logro suelto: la marca.
  final LinearGradient logro;

  static const conColor = Anillos(
    racha: LinearGradient(
      colors: [ambar, coral],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    logro: LinearGradient(
      colors: [cian, cianLuz],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
  );

  /// En grises la racha va más oscura que el logro: se siguen
  /// distinguiendo sin color.
  static const enGrises = Anillos(
    racha: LinearGradient(
      colors: [Color(0xFF262626), Color(0xFF737373)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    logro: LinearGradient(
      colors: [Color(0xFF6B7280), Color(0xFFBDBDBD)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
  );

  @override
  Anillos copyWith({LinearGradient? racha, LinearGradient? logro}) =>
      Anillos(racha: racha ?? this.racha, logro: logro ?? this.logro);

  @override
  Anillos lerp(Anillos? otro, double t) {
    if (otro == null) return this;
    return Anillos(
      racha: LinearGradient.lerp(racha, otro.racha, t)!,
      logro: LinearGradient.lerp(logro, otro.logro, t)!,
    );
  }
}

/// Los anillos del tema en uso (con color si el tema no dice nada).
Anillos anillos(BuildContext context) =>
    Theme.of(context).extension<Anillos>() ?? Anillos.conColor;

/// El tema, a partir del color que la clínica eligió en el panel.
///
/// `seedColor` y no un color fijo: Material genera de ahí una paleta
/// entera con contrastes que se leen, en claro y en oscuro. Poner el
/// color de la clínica a pelo en cada superficie daría texto gris sobre
/// fondo gris en cuanto alguien eligiera un tono claro.
///
/// Con [sinColor] la semilla no importa: la variante monocromática de
/// Material da una paleta de grises puros con los mismos contrastes.
ThemeData temaClaro([int? semilla, bool sinColor = false]) =>
    _tema(Brightness.light, semilla, sinColor);
ThemeData temaOscuro([int? semilla, bool sinColor = false]) =>
    _tema(Brightness.dark, semilla, sinColor);

ThemeData _tema(Brightness brillo, int? semilla, bool sinColor) {
  final esquema = sinColor
      ? ColorScheme.fromSeed(
          seedColor: const Color(0xFF404040),
          brightness: brillo,
          dynamicSchemeVariant: DynamicSchemeVariant.monochrome,
        )
      : ColorScheme.fromSeed(
          seedColor: semilla == null ? cian : Color(semilla),
          brightness: brillo,
        );
  return ThemeData(
    useMaterial3: true,
    colorScheme: esquema,
    extensions: [sinColor ? Anillos.enGrises : Anillos.conColor],
    scaffoldBackgroundColor: esquema.surface,
    appBarTheme: AppBarTheme(
      backgroundColor: esquema.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: esquema.onSurface,
        fontSize: 22,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.5,
      ),
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: esquema.surfaceContainerLow,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      margin: EdgeInsets.zero,
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: esquema.surface,
      indicatorColor: esquema.primaryContainer,
      elevation: 0,
      labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
    ),
    dividerTheme: const DividerThemeData(space: 1, thickness: 1),
  );
}

/// El icono de un logro, a partir de la clave corta que manda el
/// servidor. Una clave desconocida cae en la estrella en vez de dejar un
/// hueco: la clínica puede inventarse claves nuevas sin romper la app.
IconData iconoDeLogro(String clave) {
  switch (clave) {
    case 'diente':
      return Icons.medical_services_outlined;
    case 'racha':
      return Icons.local_fire_department_outlined;
    case 'corazon':
      return Icons.favorite_outline;
    case 'escudo':
      return Icons.verified_outlined;
    case 'regalo':
      return Icons.card_giftcard_outlined;
    case 'estrella':
    default:
      return Icons.star_outline;
  }
}
