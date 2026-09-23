"use client";

/**
 * Láminas anatómicas de cada pieza, como las de un atlas dental.
 * ────────────────────────────────────────────────────────────────────
 * Dos vistas por pieza, las mismas que trae cualquier ficha anatómica
 * impresa:
 *
 *   - VESTIBULAR: la pieza de frente, con su corona y sus raíces. La
 *     superior con las raíces hacia arriba y la inferior hacia abajo, de
 *     modo que las coronas se encuentran en el plano oclusal, como en la
 *     boca.
 *   - OCLUSAL: la pieza vista desde arriba, con sus cúspides y surcos, y
 *     dividida en las cinco superficies clicables del registro.
 *
 * Tres decisiones que conviene conocer antes de tocar esto:
 *
 *  1. **Medidas reales.** Ancho mesiodistal, alto de corona, largo de
 *     raíz y ancho vestibulolingual salen de las tablas de anatomía
 *     dental (Wheeler), en milímetros, y el SVG trabaja en milímetros.
 *     Por eso un incisivo inferior es la mitad de ancho que un molar y
 *     el canino tiene la raíz más larga: no es estilo, es anatomía.
 *
 *  2. **Mesial mira a la línea media.** En los cuadrantes 1 y 4 —la
 *     mitad izquierda de la pantalla— mesial queda a la derecha; en el
 *     2 y el 3, a la izquierda. Cada pieza se dibuja una sola vez en un
 *     marco canónico (mesial a la derecha, vestibular arriba en la vista
 *     oclusal, corona arriba en la vestibular) y se refleja según el
 *     cuadrante. Así la superficie que se pulsa es la que se ve.
 *
 *  3. **Cada superficie es la misma región pulsable de siempre** y emite
 *     la misma intención (`onClick(code, superficie)`). El dibujo cambia;
 *     el contrato de `contract.js`, no.
 *
 * No sustituye a `ToothArt`: ese sigue dibujando las miniaturas de la
 * ficha periodontal y dando las funciones auxiliares a la vista 3D.
 */

import { SURFACE_LABELS } from "./contract";
import { isDeciduous, isUpper } from "./ToothArt";

/* ── Medidas en milímetros ────────────────────────────────────────
   w: ancho mesiodistal · c: alto de corona · r: largo de raíz ·
   d: ancho vestibulolingual. Índice = último dígito FDI. */
const MEDIDAS = {
  permanente: {
    superior: {
      1: { w: 8.5, c: 10.5, r: 13, d: 7 },
      2: { w: 6.5, c: 9, r: 13, d: 6 },
      3: { w: 7.5, c: 10, r: 17, d: 8 },
      4: { w: 7, c: 8.5, r: 14, d: 9 },
      5: { w: 6.5, c: 8.5, r: 14, d: 9 },
      6: { w: 10, c: 7.5, r: 13, d: 11 },
      7: { w: 9, c: 7, r: 12, d: 11 },
      8: { w: 8.5, c: 6.5, r: 11, d: 10 },
    },
    inferior: {
      1: { w: 5, c: 9, r: 12.5, d: 6 },
      2: { w: 5.5, c: 9.5, r: 14, d: 6.5 },
      3: { w: 7, c: 11, r: 16, d: 7.5 },
      4: { w: 7, c: 8.5, r: 14, d: 7.5 },
      5: { w: 7, c: 8, r: 14.5, d: 8 },
      6: { w: 11, c: 7.5, r: 14, d: 10.5 },
      7: { w: 10.5, c: 7, r: 13, d: 10 },
      8: { w: 10, c: 7, r: 11, d: 9.5 },
    },
  },
  temporal: {
    superior: {
      1: { w: 6.5, c: 6, r: 10, d: 5 },
      2: { w: 5.1, c: 5.6, r: 11.4, d: 4 },
      3: { w: 7, c: 6.5, r: 13.5, d: 7 },
      4: { w: 7.3, c: 5.1, r: 10, d: 8.5 },
      5: { w: 8.2, c: 5.7, r: 11.7, d: 10 },
    },
    inferior: {
      1: { w: 4, c: 5, r: 9, d: 4 },
      2: { w: 4.5, c: 5.2, r: 10, d: 4 },
      3: { w: 5, c: 6, r: 11.5, d: 5 },
      4: { w: 7.7, c: 6, r: 9.8, d: 7 },
      5: { w: 9.9, c: 5.5, r: 11, d: 8.7 },
    },
  },
};

/** Alto de la lámina vestibular (mm): la pieza más larga de la dentición, con aire. */
export const ALTO_VESTIBULAR = { permanente: 28.2, temporal: 21 };
/** Alto reservado a la vista oclusal (mm): la pieza más ancha en sentido vestibulolingual. */
export const ALTO_OCLUSAL = { permanente: 11.8, temporal: 10.8 };

const MARGEN = 0.6; // aire en mm alrededor de cada lámina, para el contorno y el resalte

export function medidas(code) {
  const s = String(code);
  const n = Number(s.slice(-1));
  const tabla = MEDIDAS[isDeciduous(s) ? "temporal" : "permanente"][isUpper(s) ? "superior" : "inferior"];
  return tabla[n];
}

/** ¿Se dibuja reflejada en horizontal? Cuadrantes 2, 3, 6 y 7: mesial a la izquierda. */
function reflejadaX(code) {
  return ["2", "3", "6", "7"].includes(String(code)[0]);
}

/**
 * Tipo morfológico: decide el perfil de la corona, las raíces y el
 * patrón de surcos. Más fino que `toothFamily`, porque un molar
 * superior y uno inferior no se parecen en nada visto de cerca.
 */
function tipo(code) {
  const s = String(code);
  const n = Number(s.slice(-1));
  const sup = isUpper(s);
  if (isDeciduous(s)) {
    if (n <= 2) return "incisivo";
    if (n === 3) return "canino";
    if (sup) return "molarSup";
    return n === 5 ? "molarInf" : "molarInf2";
  }
  if (n <= 2) return "incisivo";
  if (n === 3) return "canino";
  if (n <= 5) return "premolar";
  if (sup) return "molarSup";
  return n === 6 ? "molarInf" : "molarInf2";
}

/* ── Curvas ─────────────────────────────────────────────────────── */

/** Spline Catmull-Rom cerrada → trayecto SVG. Pasa por todos los puntos. */
function curvaCerrada(pts, tension = 1) {
  const n = pts.length;
  const f = (v) => v.toFixed(2);
  let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i];
    const p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    const c1 = [p1[0] + ((p2[0] - p0[0]) / 6) * tension, p1[1] + ((p2[1] - p0[1]) / 6) * tension];
    const c2 = [p2[0] - ((p3[0] - p1[0]) / 6) * tension, p2[1] - ((p3[1] - p1[1]) / 6) * tension];
    d += ` C${f(c1[0])} ${f(c1[1])} ${f(c2[0])} ${f(c2[1])} ${f(p2[0])} ${f(p2[1])}`;
  }
  return `${d} Z`;
}

/** Polígono (recto) → trayecto SVG. */
function poligono(pts) {
  return `M${pts.map(([x, y]) => `${x.toFixed(2)} ${y.toFixed(2)}`).join(" L")} Z`;
}

/* ── Vista vestibular ───────────────────────────────────────────────
   Marco canónico: corona arriba (borde oclusal en y = MARGEN), raíz
   hacia abajo, mesial a la derecha (x = w). */

function perfilCorona(t, w, c, y0) {
  const X = (f) => f * w;
  const Y = (f) => y0 + f * c;
  switch (t) {
    case "incisivo":
      // Borde incisal casi recto; ángulo mesial más vivo que el distal.
      return [[X(0.03), Y(0.24)], [X(0.12), Y(0.07)], [X(0.5), Y(0.02)], [X(0.88), Y(0)], [X(0.985), Y(0.1)]];
    case "canino":
      // Cúspide única, algo mesial; la vertiente distal es la más larga.
      return [[X(0.02), Y(0.4)], [X(0.2), Y(0.2)], [X(0.54), Y(0)], [X(0.84), Y(0.16)], [X(0.985), Y(0.3)]];
    case "premolar":
      return [[X(0.02), Y(0.34)], [X(0.2), Y(0.13)], [X(0.5), Y(0)], [X(0.8), Y(0.12)], [X(0.985), Y(0.28)]];
    case "molarSup":
    case "molarInf2":
      // Dos cúspides vestibulares con el surco entre ellas.
      return [[X(0.02), Y(0.3)], [X(0.12), Y(0.1)], [X(0.3), Y(0.02)], [X(0.5), Y(0.17)],
              [X(0.72), Y(0)], [X(0.9), Y(0.08)], [X(0.985), Y(0.26)]];
    default:
      // Primer molar inferior: tres cúspides vestibulares (MV, DV y D).
      return [[X(0.02), Y(0.3)], [X(0.1), Y(0.11)], [X(0.2), Y(0.05)], [X(0.34), Y(0.16)],
              [X(0.5), Y(0.03)], [X(0.64), Y(0.15)], [X(0.8), Y(0)], [X(0.93), Y(0.09)], [X(0.99), Y(0.26)]];
  }
}

function geometriaVestibular(code) {
  const { w, c, r } = medidas(code);
  const t = tipo(code);
  const y0 = MARGEN;
  const yc = y0 + c;                                   // límite amelocementario, en el centro
  const caida = c * 0.12;                              // el cuello es convexo hacia la raíz
  const molar = t.startsWith("molar");
  const cw = w * (molar ? 0.78 : 0.66);                // ancho cervical
  const xl = (w - cw) / 2, xr = w - (w - cw) / 2;
  const lerp = (a, b, f) => a + (b - a) * f;

  const oclusal = perfilCorona(t, w, c, y0);
  const primero = oclusal[0][1], ultimo = oclusal[oclusal.length - 1][1];
  const corona = [
    [xl, yc - caida],
    [lerp(xl, 0, 0.5), y0 + c * 0.78],
    [-0.02 * w, Math.max(primero + c * 0.12, y0 + c * 0.36)],   // contacto distal
    ...oclusal,
    [w * 1.01, Math.max(ultimo + c * 0.1, y0 + c * 0.3)],       // contacto mesial
    [lerp(xr, w, 0.5), y0 + c * 0.78],
    [xr, yc - caida],
    [lerp(xl, xr, 0.72), yc - caida * 0.3],
    [lerp(xl, xr, 0.5), yc],
    [lerp(xl, xr, 0.28), yc - caida * 0.3],
  ];

  const temporal = isDeciduous(code);
  const sup = isUpper(code);
  const raices = [];      // [{ d, atras }]
  const debajo = yc - caida - 0.4;      // la raíz arranca bajo la corona, sin rendija

  const unaRaiz = (x0, x1, largo, inclinacion = -0.06) => {
    const ancho = x1 - x0;
    const apx = (x0 + x1) / 2 + inclinacion * w;        // el ápice se inclina a distal
    return curvaCerrada([
      [x0 + 0.05, yc - caida], [x0 + ancho * 0.07, yc + largo * 0.38],
      [apx - ancho * 0.2, yc + largo * 0.86], [apx, yc + largo],
      [apx + ancho * 0.2, yc + largo * 0.86], [x1 - ancho * 0.09, yc + largo * 0.38],
      [x1 - 0.05, yc - caida], [(x0 + x1) / 2, debajo],
    ]);
  };

  const dosRaices = (largo, tronco, abertura) => {
    const xm = (xl + xr) / 2;
    const dApx = xl + cw * 0.14 - abertura;
    const mApx = xr - cw * 0.16 + abertura * 0.6;
    const ft = yc + tronco;
    return curvaCerrada([
      [xl + 0.05, yc - caida], [xl - abertura * 0.4, yc + largo * 0.42],
      [dApx - 0.8, yc + largo * 0.86], [dApx, yc + largo * 0.95],
      [dApx + 1.0, yc + largo * 0.84], [xm - 0.7, ft + 1.4], [xm, ft],
      [xm + 0.7, ft + 1.4], [mApx - 1.0, yc + largo * 0.88], [mApx, yc + largo],
      [mApx + 0.8, yc + largo * 0.9], [xr + abertura * 0.4, yc + largo * 0.42],
      [xr - 0.05, yc - caida], [xm, debajo],
    ], 0.9);
  };

  // Las temporales abren las raíces para alojar el germen de la definitiva.
  const abertura = temporal ? w * 0.14 : 0;
  if (t === "molarSup") {
    // La palatina queda detrás de las dos vestibulares y es la más larga.
    raices.push({ d: unaRaiz(xl + cw * 0.2, xr - cw * 0.2, r, 0.02), atras: true });
    raices.push({ d: dosRaices(r * 0.86, r * (temporal ? 0.12 : 0.3), abertura) });
  } else if (t === "molarInf" || t === "molarInf2") {
    raices.push({ d: dosRaices(r, r * (temporal ? 0.1 : 0.28), abertura) });
  } else if (t === "premolar" && sup && String(code).slice(-1) === "4") {
    // Primer premolar superior: bifurcado en el tercio apical.
    raices.push({ d: dosRaices(r, r * 0.55, -w * 0.08) });
  } else {
    raices.push({ d: unaRaiz(xl, xr, r) });
  }

  // Relieve de la cara vestibular: el detalle que hace leer la pieza.
  const relieve = [];
  if (t === "incisivo") {
    relieve.push(`M${w * 0.36} ${y0 + c * 0.12} Q${w * 0.35} ${y0 + c * 0.45} ${w * 0.4} ${y0 + c * 0.7}`);
    relieve.push(`M${w * 0.64} ${y0 + c * 0.1} Q${w * 0.65} ${y0 + c * 0.45} ${w * 0.6} ${y0 + c * 0.7}`);
  } else if (t === "molarSup" || t === "molarInf2") {
    relieve.push(`M${w * 0.5} ${y0 + c * 0.2} Q${w * 0.52} ${y0 + c * 0.42} ${w * 0.5} ${y0 + c * 0.6}`);
  } else if (t === "molarInf") {
    relieve.push(`M${w * 0.64} ${y0 + c * 0.18} Q${w * 0.66} ${y0 + c * 0.42} ${w * 0.63} ${y0 + c * 0.58}`);
    relieve.push(`M${w * 0.34} ${y0 + c * 0.19} Q${w * 0.35} ${y0 + c * 0.36} ${w * 0.33} ${y0 + c * 0.48}`);
  }

  return {
    w, c, t, corona: curvaCerrada(corona), raices, relieve,
    brillo: { cx: w * 0.44, cy: y0 + c * 0.38, rx: w * 0.16, ry: c * 0.26 },
  };
}

/**
 * La pieza vista de frente.
 *
 * @param estado  { color, label } dominante, o null si está sana
 * @param escala  píxeles por milímetro
 */
export function VistaVestibular({ code, estado, seleccionado, escala, onClick }) {
  const g = geometriaVestibular(code);
  const temporal = isDeciduous(code);
  const H = ALTO_VESTIBULAR[temporal ? "temporal" : "permanente"];
  const anterior = g.t === "incisivo" || g.t === "canino";
  const vbX = -MARGEN, vbW = g.w + 2 * MARGEN;
  const cx = g.w / 2, cy = H / 2;
  const sx = reflejadaX(code) ? -1 : 1;
  const sy = isUpper(code) ? -1 : 1;           // superior: raíces hacia arriba
  const id = `anat-v-${code}`;

  return (
    <svg width={vbW * escala} height={H * escala} viewBox={`${vbX} 0 ${vbW} ${H}`}
         role="img" aria-label={`Pieza ${code}${estado?.label ? ` — ${estado.label}` : ""}`}
         onClick={onClick}
         style={{
           display: "block", cursor: onClick ? "pointer" : "default", overflow: "visible",
           filter: seleccionado ? "drop-shadow(0 0 2.5px var(--petrol))" : "none",
           transition: "filter var(--dur-fast) var(--ease)",
         }}>
      <title>{`Pieza ${code}${estado?.label ? ` — ${estado.label}` : ""}`}</title>
      <defs>
        {/* Esmalte: el borde incisal de los anteriores es translúcido y
            azulado; hacia el cuello gana croma porque el esmalte adelgaza
            y asoma la dentina. */}
        <linearGradient id={`${id}-esm`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={anterior ? "var(--anat-incisal)" : "var(--anat-esmalte-claro)"} />
          <stop offset={anterior ? "16%" : "10%"} stopColor="var(--anat-esmalte-claro)" />
          <stop offset="62%" stopColor="var(--anat-esmalte)" />
          <stop offset="100%" stopColor="var(--anat-esmalte-cuello)" />
        </linearGradient>
        <linearGradient id={`${id}-raiz`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--anat-raiz)" />
          <stop offset="100%" stopColor="var(--anat-raiz-apice)" />
        </linearGradient>
        {/* Volumen: los bordes proximales caen en sombra. */}
        <linearGradient id={`${id}-vol`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--anat-sombra)" />
          <stop offset="24%" stopColor="var(--anat-sombra)" stopOpacity="0" />
          <stop offset="76%" stopColor="var(--anat-sombra)" stopOpacity="0" />
          <stop offset="100%" stopColor="var(--anat-sombra)" />
        </linearGradient>
        <radialGradient id={`${id}-brillo`}>
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.75" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g transform={`translate(${cx} ${cy}) scale(${sx} ${sy}) translate(${-cx} ${-cy})`}>
        {g.raices.map((rz, i) => (
          <g key={i} opacity={rz.atras ? 0.8 : 1}>
            <path d={rz.d} fill={`url(#${id}-raiz)`} stroke="var(--anat-contorno)"
                  strokeWidth="0.2" strokeLinejoin="round" />
            <path d={rz.d} fill={`url(#${id}-vol)`} />
          </g>
        ))}

        <path d={g.corona} fill={`url(#${id}-esm)`} />
        <path d={g.corona} fill={`url(#${id}-vol)`} />
        <ellipse cx={g.brillo.cx} cy={g.brillo.cy} rx={g.brillo.rx} ry={g.brillo.ry}
                 fill={`url(#${id}-brillo)`} />
        {g.relieve.map((d, i) => (
          <path key={i} d={d} fill="none" stroke="var(--anat-surco)" strokeWidth="0.22"
                strokeLinecap="round" opacity="0.45" />
        ))}

        {/* Estado clínico sobre la corona, translúcido para no borrar la anatomía. */}
        {estado?.color && <path d={g.corona} fill={estado.color} opacity="0.58" />}

        <path d={g.corona} fill="none"
              stroke={seleccionado ? "var(--petrol)" : "var(--anat-contorno)"}
              strokeWidth={seleccionado ? 0.45 : 0.22} strokeLinejoin="round" />
      </g>
    </svg>
  );
}

/* ── Vista oclusal ──────────────────────────────────────────────────
   Marco canónico: vestibular arriba (y negativa), lingual/palatino
   abajo, mesial a la derecha. El contorno es una superelipse deformada
   —convergencia lingual y romboide del molar superior— muestreada cada
   5°, de modo que los límites entre superficies (±45°, ±135°) caen
   exactamente en muestras. */

const FORMA = {
  //            n: redondez · conv: convergencia lingual · sesgo: romboide
  //            nucleo: [ancho, alto, desplazamiento] de la cara oclusal/incisal
  incisivo: { n: 2.2, conv: 0.48, sesgo: 0, nucleo: [0.7, 0.17, -0.3] },
  canino: { n: 1.8, conv: 0.24, sesgo: 0, nucleo: [0.5, 0.26, -0.14] },
  premolar: { n: 2.2, conv: 0.1, sesgo: 0, nucleo: [0.62, 0.44, 0] },
  molarSup: { n: 2.8, conv: 0.05, sesgo: 0.2, nucleo: [0.62, 0.54, 0] },
  molarInf: { n: 2.9, conv: 0.14, sesgo: 0, nucleo: [0.64, 0.52, 0] },
  molarInf2: { n: 2.9, conv: 0.12, sesgo: 0, nucleo: [0.62, 0.52, 0] },
};

const PASOS = 72;   // 5° por muestra
const SECTORES = {
  // Índices de muestra: θ = -180° + 5°·i
  vestibular: [9, 27],
  mesial: [27, 45],
  palatal_lingual: [45, 63],
  distal: [63, 81],
};

function geometriaOclusal(code) {
  const { w, d } = medidas(code);
  const t = tipo(code);
  const sup = isUpper(code);
  const forma = { ...FORMA[t] };
  // El premolar inferior es más asimétrico: cúspide lingual pequeña.
  if (t === "premolar" && !sup) forma.conv = 0.28;
  const a = w / 2, b = d / 2, cx = 0, cy = 0;

  // Misma deformación para el contorno, el núcleo y los surcos: así los
  // detalles caen donde deben aunque el contorno sea un romboide.
  const P = (u, v) => [
    cx + a * u * (1 - forma.conv * Math.max(0, v)) - forma.sesgo * b * v,
    cy + b * v,
  ];
  const pot = (x, e) => Math.sign(x) * Math.abs(x) ** e;

  const exterior = [], interior = [];
  const [nx, ny, ndy] = forma.nucleo;
  for (let i = 0; i < PASOS; i++) {
    const th = -Math.PI + (i * 2 * Math.PI) / PASOS;
    const u = pot(Math.cos(th), 2 / forma.n), v = pot(Math.sin(th), 2 / forma.n);
    exterior.push(P(u, v));
    interior.push(P(u * nx, v * ny + ndy));
  }

  const tramo = (i0, i1) => {
    const idx = [];
    for (let i = i0; i <= i1; i++) idx.push(i % PASOS);
    return idx;
  };
  const regiones = {};
  for (const [sup_, [i0, i1]] of Object.entries(SECTORES)) {
    const idx = tramo(i0, i1);
    regiones[sup_] = poligono([...idx.map((i) => exterior[i]), ...idx.reverse().map((i) => interior[i])]);
  }
  regiones.occlusal = poligono(interior);

  // Surcos y cúspides en coordenadas (u, v) del marco canónico.
  const L = (...pts) => pts.map(([u, v], i) => {
    const [x, y] = P(u, v);
    return `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }).join(" ");
  let surcos = [], cuspides = [], fosas = [];
  switch (t) {
    case "incisivo":
      surcos = [L([-0.62, -0.3], [0.62, -0.3])];                              // borde incisal
      cuspides = [[0, 0.62]];                                                // cíngulo
      surcos.push(L([-0.5, -0.12], [-0.22, 0.48]), L([0.5, -0.12], [0.22, 0.48]));  // rebordes marginales
      break;
    case "canino":
      surcos = [L([-0.72, -0.02], [0.04, -0.2], [0.74, -0.06]), L([0.04, -0.2], [0, 0.6])];
      cuspides = [[0.04, -0.22], [0, 0.66]];
      break;
    case "premolar":
      surcos = [L([-0.48, sup ? 0.02 : 0.14], [0.48, sup ? 0.02 : 0.14])];
      fosas = [[-0.48, sup ? 0.02 : 0.14], [0.48, sup ? 0.02 : 0.14]];
      cuspides = [[0, -0.46], [0, sup ? 0.5 : 0.56]];
      if (!sup && String(code).slice(-1) === "5") {
        // Segundo premolar inferior: tres cúspides, surco en «Y».
        surcos.push(L([0, 0.14], [0, 0.72]));
        cuspides = [[0, -0.46], [0.36, 0.5], [-0.36, 0.5]];
      }
      break;
    case "molarSup":
      // Fosa central, surco vestibular, puente oblicuo y surco distopalatino.
      surcos = [
        L([0.56, -0.12], [0.12, 0.02], [-0.04, -0.12], [-0.06, -0.86]),
        L([0.12, 0.02], [-0.02, 0.18]),
        L([-0.52, 0.12], [-0.3, 0.3], [-0.36, 0.86]),
      ];
      fosas = [[0.56, -0.12], [0.12, 0.02], [-0.3, 0.3]];
      cuspides = [[0.44, -0.5], [-0.4, -0.5], [0.34, 0.46], [-0.5, 0.52]];
      break;
    case "molarInf":
      surcos = [
        L([-0.7, -0.02], [-0.36, 0.06], [0.06, -0.02], [0.4, 0.06], [0.7, -0.02]),
        L([0.16, 0.02], [0.12, -0.9]),
        L([-0.36, 0.06], [-0.46, -0.86]),
        L([0.06, -0.02], [0.02, 0.92]),
      ];
      fosas = [[-0.7, -0.02], [0.06, -0.02], [0.7, -0.02]];
      cuspides = [[0.5, -0.46], [-0.08, -0.5], [-0.58, -0.36], [0.44, 0.46], [-0.36, 0.46]];
      break;
    default: // molarInf2: cuatro cúspides, surco en cruz
      surcos = [
        L([-0.7, 0], [0.7, 0]),
        L([0, 0], [0, -0.9]),
        L([0, 0], [0, 0.9]),
      ];
      fosas = [[-0.7, 0], [0, 0], [0.7, 0]];
      cuspides = [[0.44, -0.46], [-0.44, -0.46], [0.44, 0.46], [-0.44, 0.46]];
  }

  const xs = exterior.map((p) => p[0]), ys = exterior.map((p) => p[1]);
  const caja = {
    x: Math.min(...xs) - MARGEN / 2, y: Math.min(...ys) - MARGEN / 2,
    w: Math.max(...xs) - Math.min(...xs) + MARGEN, h: Math.max(...ys) - Math.min(...ys) + MARGEN,
  };
  return {
    a, b, caja, regiones, contorno: curvaCerrada(exterior),
    surcos,
    fosas: fosas.map(([u, v]) => P(u, v)),
    cuspides: cuspides.map(([u, v]) => P(u, v)),
  };
}

// La superficie seleccionada se dibuja la última para que su contorno no
// quede tapado por la vecina.
const ORDEN = ["vestibular", "mesial", "palatal_lingual", "distal", "occlusal"];

/**
 * La pieza vista desde oclusal, con sus cinco superficies pulsables.
 */
export function VistaOclusal({ code, surfaces, selected, selectedSurface, escala, onClick }) {
  const g = geometriaOclusal(code);
  const sx = reflejadaX(code) ? -1 : 1;
  const sy = isUpper(code) ? 1 : -1;          // inferior: vestibular hacia abajo
  const id = `anat-o-${code}`;
  const orden = selected && selectedSurface && ORDEN.includes(selectedSurface)
    ? [...ORDEN.filter((s) => s !== selectedSurface), selectedSurface]
    : ORDEN;
  const radioCuspide = Math.min(g.a, g.b) * 0.42;

  return (
    <svg width={g.caja.w * escala} height={g.caja.h * escala}
         viewBox={`${g.caja.x} ${g.caja.y} ${g.caja.w} ${g.caja.h}`}
         aria-label={`Superficies de la pieza ${code}`}
         style={{ display: "block", overflow: "visible" }}>
      <defs>
        {/* En espacio de usuario, centrado en la pieza: el degradado sigue
            continuo al pasar de una superficie a otra. */}
        <radialGradient id={`${id}-esm`} gradientUnits="userSpaceOnUse" cx="0" cy="0"
                        r={Math.max(g.a, g.b) * 1.05}>
          <stop offset="0%" stopColor="var(--anat-esmalte-claro)" />
          <stop offset="62%" stopColor="var(--anat-esmalte)" />
          <stop offset="100%" stopColor="var(--anat-esmalte-cuello)" />
        </radialGradient>
        <radialGradient id={`${id}-cusp`}>
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.7" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>

      <g transform={`scale(${sx} ${sy})`}>
        {orden.map((s) => {
          const st = surfaces?.[s];
          const activa = selected && selectedSurface === s;
          return (
            <path key={s} d={g.regiones[s]}
                  fill={st?.color || `url(#${id}-esm)`}
                  fillOpacity={st?.color ? 0.88 : 1}
                  stroke={activa ? "var(--petrol)" : "var(--anat-division)"}
                  strokeWidth={activa ? 0.5 : 0.12}
                  strokeLinejoin="round"
                  onClick={(e) => { e.stopPropagation(); onClick(code, s); }}
                  style={{ cursor: "pointer" }}>
              <title>{`Pieza ${code} — ${SURFACE_LABELS[s]}${st?.label ? `: ${st.label}` : ""}`}</title>
            </path>
          );
        })}

        {/* Relieve: no intercepta clics, para que se pulse la superficie de debajo. */}
        <g pointerEvents="none">
          {g.cuspides.map(([x, y], i) => (
            <circle key={`c${i}`} cx={x} cy={y} r={radioCuspide} fill={`url(#${id}-cusp)`} />
          ))}
          {g.surcos.map((d, i) => (
            <path key={`s${i}`} d={d} fill="none" stroke="var(--anat-surco)"
                  strokeWidth="0.24" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
          ))}
          {g.fosas.map(([x, y], i) => (
            <circle key={`f${i}`} cx={x} cy={y} r="0.28" fill="var(--anat-surco)" opacity="0.55" />
          ))}
          <path d={g.contorno} fill="none"
                stroke={selected ? "var(--petrol)" : "var(--anat-contorno)"}
                strokeWidth={selected ? 0.4 : 0.22} />
        </g>
      </g>
    </svg>
  );
}
