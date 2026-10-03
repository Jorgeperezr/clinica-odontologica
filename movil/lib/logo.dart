/// El logotipo de Clinube, dibujado.
///
/// Son los MISMOS trazados que usa el panel (`frontend/lib/marca.js`):
/// «clinube» en DM Sans Bold (licencia SIL OFL) convertida a contornos.
/// Como texto dependería de una tipografía que la app no lleva, y como
/// imagen haría falta un paquete de SVG; así es idéntico en todas partes
/// y no suma dependencias.
///
/// «cli» va en el color de las letras; «nube» y el punto de la i, en el
/// de acento. Con «Sin color» los dos salen del tema en grises y el
/// logotipo no cambia en nada más.
library;

import 'package:flutter/material.dart';

const _cli = 'M304 12Q227 12 168 -21.5Q109 -55 76 -113.5Q43 -172 43 -248'
    'Q43 -324 76.5 -382.5Q110 -441 169 -474.5Q228 -508 304 -508'
    'Q400 -508 466 -458Q532 -408 549 -320L407 -320Q398 -354 370 -373.5'
    'Q342 -393 303 -393Q268 -393 240.5 -376Q213 -359 197 -326.5'
    'Q181 -294 181 -248Q181 -214 190 -187.5Q199 -161 215.5 -142'
    'Q232 -123 254.5 -113Q277 -103 303 -103Q329 -103 350 -111.5'
    'Q371 -120 386 -136.5Q401 -153 407 -176L549 -176Q532 -90 466 -39'
    'Q400 12 304 12ZM617 0L617 -715L752 -715L752 0ZM836 0L836 -496L971 -496'
    'L971 0Z';

const _nube =
    'M1053 0L1053 -496L1171 -496L1181 -413L1182 -413Q1206 -457 1248.5 -482.5'
    'Q1291 -508 1351 -508Q1413 -508 1456 -481.5Q1499 -455 1522 -404'
    'Q1545 -353 1545 -278L1545 0L1410 0L1410 -266Q1410 -328 1385 -361'
    'Q1360 -394 1306 -394Q1271 -394 1244.5 -377.5Q1218 -361 1203 -330.5'
    'Q1188 -300 1188 -256L1188 0ZM1806 12Q1745 12 1701.5 -14'
    'Q1658 -40 1635 -91.5Q1612 -143 1612 -218L1612 -496L1747 -496L1747 -230'
    'Q1747 -168 1772 -135Q1797 -102 1851 -102Q1886 -102 1912.5 -118.5'
    'Q1939 -135 1954 -165.5Q1969 -196 1969 -240L1969 -496L2104 -496L2104 0'
    'L1986 0L1976 -82L1975 -82Q1951 -39 1908.5 -13.5Q1866 12 1806 12ZM2488 12'
    'Q2450 12 2418.5 2Q2387 -8 2362.5 -26.5Q2338 -45 2320 -71L2319 -71L2306 0'
    'L2188 0L2188 -715L2323 -715L2323 -428Q2347 -460 2386.5 -484'
    'Q2426 -508 2487 -508Q2558 -508 2612.5 -474Q2667 -440 2698 -381.5'
    'Q2729 -323 2729 -247Q2729 -173 2698 -114Q2667 -55 2612.5 -21.5'
    'Q2558 12 2488 12ZM2456 -104Q2496 -104 2526.5 -122.5'
    'Q2557 -141 2574.5 -173.5Q2592 -206 2592 -248Q2592 -290 2574.5 -322.5'
    'Q2557 -355 2526.5 -373.5Q2496 -392 2456 -392Q2416 -392 2385 -373.5'
    'Q2354 -355 2336.5 -322.5Q2319 -290 2319 -248Q2319 -206 2336.5 -173.5'
    'Q2354 -141 2385 -122.5Q2416 -104 2456 -104ZM3039 12Q2963 12 2904.5 -20'
    'Q2846 -52 2813 -110Q2780 -168 2780 -243Q2780 -321 2812.5 -380.5'
    'Q2845 -440 2903.5 -474Q2962 -508 3040 -508Q3114 -508 3170.5 -476'
    'Q3227 -444 3258.5 -388.5Q3290 -333 3290 -263Q3290 -253 3290 -240.5'
    'Q3290 -228 3288 -215L2877 -215L2877 -298L3153 -298Q3150 -344 3118.5 -372'
    'Q3087 -400 3040 -400Q3005 -400 2976 -384.5Q2947 -369 2930 -337.5'
    'Q2913 -306 2913 -259L2913 -230Q2913 -190 2929 -160Q2945 -130 2973.5 -114'
    'Q3002 -98 3038 -98Q3075 -98 3100 -114.5Q3125 -131 3138 -157L3276 -157'
    'Q3261 -110 3228 -71.5Q3195 -33 3147 -10.5Q3099 12 3039 12Z';

const _c = 'M304 12Q227 12 168 -21.5Q109 -55 76 -113.5Q43 -172 43 -248'
    'Q43 -324 76.5 -382.5Q110 -441 169 -474.5Q228 -508 304 -508'
    'Q400 -508 466 -458Q532 -408 549 -320L407 -320Q398 -354 370 -373.5'
    'Q342 -393 303 -393Q268 -393 240.5 -376Q213 -359 197 -326.5'
    'Q181 -294 181 -248Q181 -214 190 -187.5Q199 -161 215.5 -142'
    'Q232 -123 254.5 -113Q277 -103 303 -103Q329 -103 350 -111.5'
    'Q371 -120 386 -136.5Q401 -153 407 -176L549 -176Q532 -90 466 -39'
    'Q400 12 304 12Z';

// cx, cy, r del punto y caja (x, y, ancho, alto), en unidades de la fuente.
const _punto = [903.5, -628.0, 90.0];
const _caja = [43.0, -718.0, 3247.0, 730.0];
const _puntoIcono = [667.0, -612.0, 112.0];
const _cajaIcono = [43.0, -724.0, 736.0, 736.0];

/// «clinube» completo. [alto] en píxeles lógicos; el ancho sale solo.
class LogoClinube extends StatelessWidget {
  const LogoClinube({super.key, this.alto = 32, this.tinta, this.acento});

  final double alto;

  /// Color de «cli». Por omisión, el del texto del tema.
  final Color? tinta;

  /// Color de «nube» y del punto. Por omisión, el principal del tema.
  final Color? acento;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return Semantics(
      label: 'Clinube',
      image: true,
      child: CustomPaint(
        size: Size(alto * _caja[2] / _caja[3], alto),
        painter: _Pintor(
          caja: _caja,
          trazos: [
            (_cli, tinta ?? esquema.onSurface),
            (_nube, acento ?? esquema.primary)
          ],
          punto: _punto,
          colorPunto: acento ?? esquema.primary,
        ),
      ),
    );
  }
}

/// La «c» con el punto: el icono de la app.
class IconoClinube extends StatelessWidget {
  const IconoClinube({super.key, this.alto = 24, this.tinta, this.acento});

  final double alto;
  final Color? tinta;
  final Color? acento;

  @override
  Widget build(BuildContext context) {
    final esquema = Theme.of(context).colorScheme;
    return CustomPaint(
      size: Size(alto * _cajaIcono[2] / _cajaIcono[3], alto),
      painter: _Pintor(
        caja: _cajaIcono,
        trazos: [(_c, tinta ?? esquema.onSurface)],
        punto: _puntoIcono,
        colorPunto: acento ?? esquema.primary,
      ),
    );
  }
}

class _Pintor extends CustomPainter {
  _Pintor(
      {required this.caja,
      required this.trazos,
      required this.punto,
      required this.colorPunto});

  final List<double> caja;
  final List<(String, Color)> trazos;
  final List<double> punto;
  final Color colorPunto;

  @override
  void paint(Canvas canvas, Size size) {
    final escala = size.height / caja[3];
    canvas
      ..save()
      ..scale(escala)
      ..translate(-caja[0], -caja[1]);
    for (final (d, color) in trazos) {
      canvas.drawPath(trazado(d), Paint()..color = color);
    }
    canvas
      ..drawCircle(
          Offset(punto[0], punto[1]), punto[2], Paint()..color = colorPunto)
      ..restore();
  }

  @override
  bool shouldRepaint(_Pintor viejo) =>
      viejo.colorPunto != colorPunto ||
      viejo.trazos.length != trazos.length ||
      [
        for (var i = 0; i < trazos.length; i++)
          viejo.trazos[i].$2 != trazos[i].$2
      ].any((x) => x);
}

/// Interpreta los trazados: solo M, L, Q y Z absolutos, que es lo único
/// que sale del conversor. Cualquier otra letra es un error de quien
/// regeneró las cadenas, y se dice en vez de dibujar un garabato.
Path trazado(String d) {
  final path = Path();
  final fichas = RegExp(r'[MLQZ]|-?\d+(?:\.\d+)?')
      .allMatches(d)
      .map((m) => m.group(0)!)
      .toList();
  var i = 0;
  double n() => double.parse(fichas[i++]);
  while (i < fichas.length) {
    final orden = fichas[i++];
    switch (orden) {
      case 'M':
        path.moveTo(n(), n());
      case 'L':
        path.lineTo(n(), n());
      case 'Q':
        path.quadraticBezierTo(n(), n(), n(), n());
      case 'Z':
        path.close();
      default:
        throw FormatException('Orden de trazado inesperada: $orden');
    }
  }
  return path;
}
