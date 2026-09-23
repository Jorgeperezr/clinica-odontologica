/// El aspecto de la app.
///
/// La dinámica es la de Instagram —una fila de círculos arriba, un muro
/// de tarjetas debajo, cinco pestañas al pie— pero los colores no: aquí
/// el azul petróleo y el menta del panel de la clínica, que es lo que el
/// paciente asocia con su odontólogo, no una red social.
///
/// Los degradados de los anillos tampoco son los de Instagram. Dicen
/// algo: el ámbar/coral es para las rachas vivas, el petróleo para un
/// logro suelto, y el gris para los que todavía no se han ganado.
library;

import 'package:flutter/material.dart';

const petroleo = Color(0xFF14607A);
const petroleoHondo = Color(0xFF0C4256);
const menta = Color(0xFF3FB8A0);
const ambar = Color(0xFFE0922F);
const coral = Color(0xFFE2603F);

/// Anillo de una racha viva: llama.
const anilloRacha = LinearGradient(
  colors: [ambar, coral],
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
);

/// Anillo de un logro suelto: la marca de la clínica.
const anilloLogro = LinearGradient(
  colors: [petroleo, menta],
  begin: Alignment.topLeft,
  end: Alignment.bottomRight,
);

/// El tema, a partir del color que la clínica eligió en el panel.
///
/// `seedColor` y no un color fijo: Material genera de ahí una paleta
/// entera con contrastes que se leen, en claro y en oscuro. Poner el
/// color de la clínica a pelo en cada superficie daría texto gris sobre
/// fondo gris en cuanto alguien eligiera un tono claro.
ThemeData temaClaro([int? semilla]) => _tema(Brightness.light, semilla);
ThemeData temaOscuro([int? semilla]) => _tema(Brightness.dark, semilla);

ThemeData _tema(Brightness brillo, [int? semilla]) {
  final esquema = ColorScheme.fromSeed(
    seedColor: semilla == null ? petroleo : Color(semilla),
    brightness: brillo,
  );
  return ThemeData(
    useMaterial3: true,
    colorScheme: esquema,
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
