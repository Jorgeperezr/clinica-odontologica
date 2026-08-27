"use client";

/**
 * Geometría dental anatómica (Sprint 49 · refinada en Sprints 53 y 54).
 * ────────────────────────────────────────────────────────────────────
 * Las piezas se generan por "lofting": se apilan secciones transversales
 * a lo largo del eje del diente y se cosen en una superficie continua
 * con normales suavizadas.
 *
 * SISTEMA DE COORDENADAS LOCAL (importante: lo asume el contenedor 3D)
 *
 *   +X  mesio-distal   → a lo largo de la arcada
 *   +Z  vestibular     → hacia fuera de la boca
 *   +Y  oclusal        → la corona SIEMPRE se construye hacia arriba
 *
 * La arcada superior no necesita una malla propia: el contenedor gira la
 * pieza 180° sobre su eje Z, que invierte corona y raíz conservando el
 * lado vestibular. Gracias a eso la geometría solo depende de la FAMILIA
 * (más el número de raíces y la variante oclusal) y se puede reutilizar
 * entre piezas equivalentes: de 52 mallas únicas se pasa a unas doce.
 * Las diferencias de tamaño entre piezas de una misma familia se aplican
 * como escala del objeto (`toothScale`), que no rompe esa reutilización.
 *
 * ANATOMÍA QUE SE MODELA
 *
 *   · Sección transversal por familia (superelipse): el molar tiende al
 *     cuadrado redondeado, el incisivo es una lámina aplanada.
 *   · Perfil vertical real: ecuador en el tercio medio, constricción
 *     cervical y raíces que afinan hasta el ápice con curvatura distal.
 *   · Cara oclusal con relieve verdadero —cúspides, fosa central, surcos
 *     de desarrollo, rebordes marginales y cresta oblicua— resuelta como
 *     un campo de altura H(u,w), no como una tapa.
 *   · Oclusión ambiental HORNEADA en el color de vértice: las fosas y los
 *     surcos se oscurecen solos. Es lo que hace que las fisuras se lean
 *     como surcos y no como un dibujo plano, y no cuesta nada en tiempo
 *     de ejecución.
 *   · Transición continua esmalte → dentina cervical → cemento, sin el
 *     escalón que se veía antes en el cuello.
 *
 * GARANTÍA DE ESTANQUEIDAD
 * Cada parte (corona+tronco, cada raíz) es una superficie CERRADA con sus
 * tapas, y corona y raíz comparten por construcción el mismo anillo
 * cervical. Las costuras se orientan de forma explícita: la corona se
 * recorre hacia arriba y la raíz hacia abajo, así que la raíz se cose con
 * el orden de vértices invertido (si no, sus caras miran hacia dentro,
 * el descarte de caras traseras se las come y se abre un hueco negro en
 * el cuello).
 */

import { toothFamily, isUpper } from "./ToothArt";

const RADIAL = 30;        // secciones alrededor del eje
const CROWN_RINGS = 11;   // anillos de la corona
const CAP_RINGS = 5;      // anillos de la mesa oclusal
const ROOT_RINGS = 9;     // anillos de cada raíz

/**
 * Reparto de anillos agrupado en los extremos (tipo Chebyshev). La
 * curvatura se concentra en el cuello y en la cara oclusal; repartir los
 * anillos por igual gastaba resolución en el tercio medio, que es casi
 * recto, y dejaba aristas visibles justo donde más se notan.
 */
function clustered(k, n) {
  return 0.5 - 0.5 * Math.cos(Math.PI * (k / n));
}

/* Nota de coste: con el reparto agrupado se obtiene la misma suavidad
   aparente con bastantes menos anillos que repartiéndolos por igual, que
   es lo que permite subir el detalle de la cara oclusal sin disparar el
   número de triángulos. */

/**
 * Hacia dónde cae MESIAL en el eje X local. Las piezas se reparten sobre
 * la curva de derecha a izquierda, así que en los cuadrantes del lado
 * derecho del paciente (1, 4 y sus temporales 5 y 8) mesial queda en +X,
 * y en los del izquierdo en −X. Hace falta porque una corona NO es
 * simétrica: el ángulo mesioincisal es casi recto y el distoincisal
 * claramente redondeado, y el cíngulo se desplaza a distal.
 */
function mesialSign(code) {
  return ["1", "4", "5", "8"].includes(String(code)[0]) ? 1 : -1;
}

/** ¿Pieza temporal? (cuadrantes 5 a 8) */
function isDeciduous(code) {
  return ["5", "6", "7", "8"].includes(String(code)[0]);
}

/** Número de raíces según anatomía real. */
function rootCount(code) {
  const fam = toothFamily(code);
  const up = isUpper(code);
  const n = Number(String(code).slice(-1));
  if (fam === "molar") return up ? 3 : 2;
  if (fam === "premolar") return up && n === 4 ? 2 : 1;
  return 1;
}

/* Dimensiones base: [ancho mesio-distal, profundidad vestíbulo-lingual,
   alto corona, alto raíz]. Las proporciones siguen las medias de la
   anatomía dental (un incisivo central mide unos 8,5 mm de ancho por
   10,5 de corona: relación ≈ 1,24). */
function dims(code) {
  const fam = toothFamily(code);
  const dec = isDeciduous(code);
  const s = dec ? 0.78 : 1;
  const base = {
    incisivo: [0.80, 0.62, 0.98, 1.20],
    canino: [0.76, 0.72, 1.06, 1.42],
    premolar: [0.72, 0.80, 0.86, 1.15],
    molar: [1.05, 1.00, 0.84, 1.12],
  }[fam];
  return [base[0] * s, base[1] * s, base[2] * s, base[3] * (dec ? 0.62 : 1)];
}

/**
 * Proporciones de cada pieza concreta dentro de su familia, como escala
 * del objeto [mesio-distal, alto, vestíbulo-lingual]. Medias reales: el
 * lateral superior es sensiblemente menor que el central, los incisivos
 * inferiores son las piezas más estrechas de la boca, el primer molar es
 * el mayor y el cordal el más pequeño e irregular.
 */
export function toothScale(code) {
  const n = Number(String(code).slice(-1));
  const fam = toothFamily(code);
  const up = isUpper(code);
  if (fam === "incisivo") {
    if (up) return n === 2 ? [0.79, 0.88, 0.93] : [1, 1, 1];
    return n === 1 ? [0.64, 0.85, 0.80] : [0.71, 0.89, 0.83];
  }
  if (fam === "canino") return up ? [1, 1, 1] : [0.93, 0.99, 0.95];
  if (fam === "premolar") {
    if (up) return n === 5 ? [0.95, 0.94, 0.98] : [1, 1, 1];
    return n === 5 ? [1.02, 0.97, 1.02] : [0.95, 0.93, 0.96];
  }
  if (fam === "molar") {
    if (n === 7) return [0.93, 0.94, 0.96];
    if (n === 8) return [0.83, 0.86, 0.91];   // el cordal es menor y más irregular
    return up ? [1, 1, 1] : [1.06, 0.98, 0.96];  // el 1.er molar inferior es más ancho
  }
  return [1, 1, 1];
}

/**
 * Postura de la pieza en la arcada, en radianes.
 *
 *   torque → inclinación vestíbulo-lingual de la corona (positivo =
 *            corona hacia vestibular). Los valores siguen el orden de la
 *            prescripción ortodóncica habitual: incisivos superiores con
 *            torque vestibular y sectores posteriores con torque lingual
 *            creciente, muy marcado en los molares inferiores.
 *   tip    → inclinación mesio-distal de la corona.
 *   rise   → desplazamiento vertical del plano oclusal (curva de Spee).
 *
 * Sin esto todas las piezas quedan verticales y paralelas, que es el
 * rasgo que delata una arcada montada a mano.
 */
/**
 * Variación anatómica por pieza. Dos dientes de la misma persona no son
 * iguales, y una arcada de piezas idénticas se lee de inmediato como
 * generada por ordenador. Se deriva de forma DETERMINISTA del número
 * FDI: la misma pieza tiene siempre la misma variación, así que el
 * modelo no "baila" entre visitas ni entre exportaciones del informe.
 */
function hash01(code, salt) {
  let h = 2166136261 ^ salt;
  const s = String(code);
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return ((h >>> 8) & 0xffff) / 0xffff;
}

/** Desviaciones pequeñas de tamaño y aplomo, centradas en cero. */
export function toothJitter(code) {
  const j = (salt) => hash01(code, salt) * 2 - 1;
  return {
    scale: [1 + j(11) * 0.035, 1 + j(23) * 0.045, 1 + j(37) * 0.035],
    rotY: j(53) * 0.055,      // ligera rotación sobre su eje
    torque: j(67) * 0.045,    // aplomo vestíbulo-lingual
    tip: j(83) * 0.04,        // aplomo mesio-distal
    rise: j(97) * 0.018,      // altura en el plano oclusal
  };
}

export function toothPose(code) {
  const fam = toothFamily(code);
  const up = isUpper(code);
  const n = Number(String(code).slice(-1));
  const d = Math.PI / 180;

  let torque, tip, rise;
  if (up) {
    torque = { incisivo: n === 1 ? 6 : 7, canino: 2, premolar: -5, molar: -8 }[fam];
    tip = { incisivo: n === 1 ? 3.5 : 6, canino: 8, premolar: 0, molar: 4 }[fam];
    rise = { incisivo: 0, canino: 0.02, premolar: 0.05, molar: 0.09 }[fam];
  } else {
    torque = { incisivo: -1, canino: -6, premolar: n === 4 ? -11 : -14, molar: -17 }[fam];
    tip = { incisivo: 1, canino: 3, premolar: 1.5, molar: 1.5 }[fam];
    rise = { incisivo: 0, canino: 0.02, premolar: 0.05, molar: 0.10 }[fam];
  }
  if (fam === "molar" && n === 8) torque *= 1.25;   // el cordal se inclina más
  return { torque: torque * d, tip: tip * d, rise };
}

/* ── Sección transversal ─────────────────────────────────────────────
   Superelipse: el exponente controla cuánto se parece al cuadrado. El
   molar es casi rectangular con esquinas redondeadas; el incisivo, una
   lámina. Se añade la concavidad lingual y las convexidades proximales
   (áreas de contacto), que son las que hacen que dos piezas vecinas se
   toquen de forma creíble. */
/**
 * Lóbulos de desarrollo. Una corona no crece como un cilindro: se forma
 * a partir de lóbulos que se fusionan, y los surcos que quedan entre
 * ellos son lo que da a cada familia su silueta propia. Modelarlos es lo
 * que evita que incisivo, canino, premolar y molar parezcan la misma
 * geometría reescalada.
 *
 *   incisivo → tres lóbulos vestibulares (de ahí los mamelones del borde
 *              y las dos depresiones verticales de la cara) más cíngulo
 *   canino   → lóbulo medio dominante, que forma la cresta vestibular
 *   premolar → un lóbulo vestibular marcado y otro palatino menor
 *   molar    → dos vestibulares y dos palatinos, uno por cúspide
 *
 * θ = 0 mira a mesial/distal, θ = π/2 a vestibular, θ = −π/2 a lingual.
 */
const B = Math.PI / 2;      // vestibular
const L = -Math.PI / 2;     // lingual / palatino

function lobeSpec(fam, up) {
  switch (fam) {
    case "incisivo":
      return [
        { a: B - 0.62, amp: 0.055, w: 0.10 },
        { a: B, amp: 0.070, w: 0.11 },
        { a: B + 0.62, amp: 0.055, w: 0.10 },
        { a: L, amp: 0.045, w: 0.22 },
      ];
    case "canino":
      return [
        { a: B - 0.72, amp: 0.038, w: 0.10 },
        { a: B, amp: 0.115, w: 0.13 },        // cresta vestibular del canino
        { a: B + 0.72, amp: 0.038, w: 0.10 },
        { a: L, amp: 0.075, w: 0.20 },        // cíngulo marcado
      ];
    case "premolar":
      return [
        { a: B, amp: 0.105, w: 0.16 },        // cresta vestibular
        { a: L, amp: up ? 0.080 : 0.062, w: 0.19 },
      ];
    default:
      return [
        { a: B - 0.60, amp: 0.075, w: 0.115 },
        { a: B + 0.60, amp: 0.068, w: 0.115 },
        { a: L - 0.58, amp: 0.070, w: 0.120 },
        { a: L + 0.58, amp: 0.060, w: 0.120 },
      ];
  }
}

/** Diferencia angular mínima entre dos ángulos. */
function angDelta(x, y) {
  let d = (x - y) % (Math.PI * 2);
  if (d > Math.PI) d -= Math.PI * 2;
  if (d < -Math.PI) d += Math.PI * 2;
  return d;
}

/**
 * Factor de radio por lóbulos a la altura v. Los lóbulos se difuminan
 * hacia el cuello —donde la corona es lisa— y se marcan hacia el tercio
 * oclusal, que es como se forman realmente.
 */
function lobeFactor(spec, theta, v) {
  const fade = v <= 0.18 ? 0 : Math.min(1, (v - 0.18) / 0.5);
  const soft = fade * fade * (3 - 2 * fade);
  if (soft <= 0) return 1;
  let f = 1;
  for (const lo of spec) {
    const d = angDelta(theta, lo.a);
    f += lo.amp * Math.exp(-(d * d) / lo.w) * soft;
  }
  return f;
}

/**
 * Cresta cervical: el rodete que rodea la corona junto al cuello
 * (cíngulo en el sector anterior, cresta cervical vestibular en el
 * posterior). Actúa al revés que los lóbulos: máximo en el cuello.
 */
function cervicalRidge(fam, theta, v) {
  const amp = { incisivo: 0.055, canino: 0.075, premolar: 0.050, molar: 0.045 }[fam];
  const band = Math.exp(-((v - 0.22) ** 2) / 0.020);
  const dl = angDelta(theta, L), db = angDelta(theta, B);
  const lingual = Math.exp(-(dl * dl) / 0.55);
  const buccal = Math.exp(-(db * db) / 0.75) * (fam === "molar" || fam === "premolar" ? 1 : 0.35);
  return 1 + amp * band * (lingual + buccal);
}

function sectionRadius(fam, theta, a, b) {
  const n = { molar: 3.3, premolar: 2.8, canino: 2.35, incisivo: 2.2 }[fam];
  const ct = Math.cos(theta), st = Math.sin(theta);
  const r = Math.pow(
    Math.pow(Math.abs(ct) / a, n) + Math.pow(Math.abs(st) / b, n),
    -1 / n,
  );
  let out = r;
  // Concavidad lingual (z < 0) más marcada en incisivos y caninos
  if (st < 0) {
    const k = fam === "incisivo" ? 0.16 : fam === "canino" ? 0.12 : 0.05;
    out *= 1 - k * st * st;
  }
  // Convexidad proximal: refuerza el punto de contacto mesial y distal
  out *= 1 + 0.035 * ct * ct;
  return out;
}

/**
 * Perfil vertical de la corona. v = 0 en el cuello, 1 en el borde
 * oclusal. Ecuador en el tercio medio y cierre suave hacia oclusal.
 * El incisivo apenas se recoge: su borde incisal conserva casi todo el
 * ancho mesio-distal, y recortarlo lo convierte en un cono.
 */
function crownProfile(v, fam) {
  const eq = fam === "molar" ? 0.40 : 0.46;          // altura del ecuador
  const bulge = fam === "incisivo" ? 0.12 : 0.20;    // cuánto sobresale
  const close = fam === "incisivo" ? 0.07 : fam === "canino" ? 0.14 : 0.20;
  if (v <= eq) {
    /* Del cuello al ecuador. La curva arranca con pendiente CERO
       (smoothstep en vez de seno): si el diámetro crece de golpe al salir
       del cuello, la unión con la raíz forma una arista viva que se lee
       como una grieta iluminada alrededor de toda la pieza. */
    const t = v / eq;
    return 1 + bulge * (t * t * (3 - 2 * t));
  }
  const x = (v - eq) / (1 - eq);
  return 1 + bulge * (1 - x * x) - close * x * x;
}

/**
 * Achatamiento vestíbulo-lingual hacia el borde oclusal. Es la clave de
 * la forma del incisivo: la corona nace gruesa en el cuello y termina en
 * una LÁMINA. Sin esto la sección se mantiene casi circular arriba y la
 * tapa oclusal se cierra en punta, con aspecto de colmillo.
 */
function blTaper(fam, v) {
  const end = { incisivo: 0.38, canino: 0.68, premolar: 0.87, molar: 0.92 }[fam];
  return 1 - (1 - end) * Math.pow(v, 1.4);
}

/**
 * Perfil de la raíz. v = 0 en el cuello, 1 en el ápice. Arranca con
 * pendiente casi nula en el cuello (mismo motivo que la corona) y afina
 * como una raíz real hacia el ápice.
 */
function rootProfile(v) {
  return Math.pow(Math.max(0, 1 - v * v), 0.5) * 0.94 + 0.06 * (1 - v);
}

/**
 * Festón de la unión amelocementaria: el cuello sube en mesial y distal
 * y baja en vestibular y lingual. Evita el aspecto de tubo cortado a
 * máquina en la zona del cuello.
 */
function cejScallop(theta, ch) {
  return Math.cos(2 * theta) * ch * 0.05;
}

/* ── Cara oclusal ────────────────────────────────────────────────────
   Campo de altura H(u, w) sobre el plano oclusal, con u = x/semiancho y
   w = z/semiprofundidad, ambos en [-1, 1]. Devuelve altura relativa
   (0 = fondo de fosa, 1 = punta de cúspide). Modelar la cara oclusal
   como campo y no como tapa es lo que produce cúspides, fosas y surcos
   de verdad. */
function gauss(d2, k) {
  return Math.exp(-d2 / k);
}

/**
 * Variante oclusal: piezas que comparten familia y número de raíces pero
 * NO la misma cara oclusal. Entra en la clave del caché; sin esto el
 * primer molar inferior (cinco cúspides) y el segundo (cuatro) se
 * repartían la misma malla y ganaba el que se construyera primero.
 */
function occlusalVariant(code) {
  const fam = toothFamily(code);
  const n = Number(String(code).slice(-1));
  if (fam === "molar") return isUpper(code) ? "mu" : (n === 6 ? "m5" : "m4");
  /* Primero y segundo premolar tienen cara oclusal distinta, así que son
     mallas distintas. En los superiores se separaban por casualidad (el
     primero tiene dos raíces y el segundo una), pero los INFERIORES
     tienen una raíz los dos y compartían malla: ganaba el que se
     construyera primero. Mismo fallo que ya apareció en molares e
     incisivos. */
  if (fam === "premolar") return `${isUpper(code) ? "pu" : "pl"}${n === 4 ? "1" : "2"}`;
  // El lateral redondea más sus ángulos incisales que el central: es otra
  // cara oclusal y por tanto otra malla.
  if (fam === "incisivo") return n === 2 ? "i2" : "i1";
  return "-";
}

function occlusalField(fam, code) {
  const n = Number(String(code).slice(-1));
  const up = isUpper(code);
  const ms = mesialSign(code);

  if (fam === "molar") {
    /* Cuatro cúspides (MV, DV, ML, DL). El primer molar inferior suma la
       distal —son las cinco del patrón "Y5"— y el superior tiene la
       mesiolingual dominante unida a la distovestibular por la cresta
       oblicua. */
    /* Cúspides FUNCIONALES (las que ocluyen contra la fosa antagonista)
       frente a las no funcionales: en el maxilar las palatinas soportan
       la oclusión y son más altas y romas; en la mandíbula lo son las
       vestibulares. La diferencia de altura entre unas y otras es un
       rasgo clínico, no un adorno. */
    const cusps = up
      ? [{ u: -0.54, w: 0.54, a: 0.90 }, { u: 0.50, w: 0.50, a: 0.84 },
         { u: -0.52, w: -0.54, a: 1.08 }, { u: 0.52, w: -0.48, a: 0.96 }]
      : [{ u: -0.54, w: 0.52, a: 1.06 }, { u: 0.46, w: 0.54, a: 1.00 },
         { u: -0.52, w: -0.52, a: 0.88 }, { u: 0.50, w: -0.50, a: 0.82 }];
    if (!up && n === 6) cusps.push({ u: 0.84, w: 0.10, a: 0.82 });
    return (u, w) => {
      let h = 0;
      for (const c of cusps) h += c.a * gauss((u - c.u) ** 2 + (w - c.w) ** 2, 0.24);

      // Rebordes marginales mesial y distal
      h += 0.46 * gauss((Math.abs(u) - 0.88) ** 2, 0.038) * (1 - 0.5 * w * w);

      // Surcos de desarrollo principales, en cruz
      h -= 0.34 * gauss(u * u, 0.013);
      h -= 0.30 * gauss(w * w, 0.013);

      /* NOTA (Sprint 59). Se intentó ampliar el relieve molar con crestas
         triangulares, surco vestibular, fositas accesorias y fisuras
         secundarias. El conjunto RESTA legibilidad en vez de sumarla: las
         crestas rellenan los valles entre cúspides y el resultado es una
         mesa oclusal más plana que la de partida, comprobado en la vista
         oclusal. Se vuelve al relieve anterior —cúspides, fosa central,
         surcos en cruz, rebordes marginales y cresta oblicua—, que sí se
         lee. Queda pendiente rehacerlo midiendo el efecto de cada término
         por separado en vez de sumarlos todos a la vez. */

      // Cresta oblicua del molar superior: une la mesiolingual con la distovestibular
      if (up) h += 0.26 * gauss((u * 0.7 + w * 0.7) ** 2, 0.042);
      return h;
    };
  }

  if (fam === "premolar") {
    /* Dos cúspides enfrentadas con surco central mesio-distal. En los
       superiores la vestibular domina; en los inferiores la lingual es
       claramente menor, sobre todo en el primero. */
    /* Primero y segundo premolar NO comparten cara oclusal: en el
       primero la cúspide vestibular domina y el surco central es largo y
       recto; en el segundo las cúspides se equilibran y el surco es más
       corto y sinuoso. */
    const first = n === 4;
    const ling = up ? (first ? 0.78 : 0.93) : (first ? 0.54 : 0.78);
    return (u, w) => {
      // Cúspides vestibular y lingual
      let h = 1.00 * gauss(u * u * (first ? 0.42 : 0.60) + (w - 0.56) ** 2, 0.28);
      h += ling * gauss(u * u * (first ? 0.55 : 0.60) + (w + 0.54) ** 2, 0.25);
      // Crestas triangulares que bajan de cada cúspide hacia el surco
      h += 0.22 * gauss(u * u, 0.05) * gauss((Math.abs(w) - 0.32) ** 2, 0.055);
      // Rebordes marginales mesial y distal
      h += 0.44 * gauss((Math.abs(u) - 0.84) ** 2, 0.032) * (1 - 0.6 * w * w);
      /* Surco central. En el primero es largo y recto; en el segundo es
         más corto y se interrumpe en el centro, dejando dos fositas
         —mesial y distal— en vez de un canal continuo. Esa interrupción
         es lo que los distingue en la vista oclusal. */
      if (first) {
        h -= 0.42 * gauss(w * w, 0.015);
      } else {
        h -= 0.40 * gauss(w * w, 0.015) * (0.45 + 0.55 * gauss(u * u, 0.30));
        h -= 0.16 * gauss((Math.abs(u) - 0.42) ** 2, 0.020) * gauss(w * w, 0.05);
      }
      return h;
    };
  }

  if (fam === "canino") {
    /* Cúspide única desplazada a mesial, con sus dos vertientes, las
       crestas marginales y el cíngulo lingual. */
    /* La punta cae ligeramente hacia DISTAL, así que la vertiente mesial
       es corta y empinada y la distal larga y tendida. Es lo que da al
       canino su asimetría característica. */
    return (u, w) => {
      const tip = -0.12 * ms;   // desplazamiento distal de la cúspide
      let h = 1.08 * gauss((u - tip) ** 2 * 0.85 + (w - 0.06) ** 2 * 0.65, 0.28);
      // Reborde mesial más corto y marcado que el distal
      h += 0.26 * gauss((u - 0.78 * ms) ** 2, 0.045) * gauss((w + 0.2) ** 2, 0.4);
      h += 0.17 * gauss((u + 0.84 * ms) ** 2, 0.075) * gauss((w + 0.2) ** 2, 0.45);
      h += 0.34 * gauss((w + 0.74) ** 2, 0.09) * (1 - 0.7 * (u + 0.15 * ms) ** 2);
      h -= 0.20 * gauss((w + 0.36) ** 2, 0.05);                      // fosa lingual
      return Math.max(h, 0.04);
    };
  }

  /* Incisivo: borde incisal en lámina, fosa lingual y cíngulo. La
     campana en `w` es ESTRECHA a propósito: así la altura se mantiene a
     lo largo de todo el eje mesio-distal y cae de golpe hacia vestibular
     y lingual, lo que produce una arista recta —un cincel— en vez de una
     cúpula. Los mamelones se insinúan apenas, como en un diente joven, y
     los ángulos incisales se redondean algo en el lateral. */
  /* El lateral redondea bastante más sus ángulos que el central. Y en
     ambos, el ángulo MESIOINCISAL es casi recto mientras el DISTOINCISAL
     se redondea: es el rasgo que permite identificar de un vistazo si un
     incisivo es del lado derecho o del izquierdo, y sin él las dos
     hemiarcadas se ven como una imagen especular perfecta. */
  const base = n === 2 ? 0.30 : 0.18;
  const roundM = base * 0.5, roundD = base * 1.9;
  return (u, w) => {
    const mesialSide = u * ms > 0;
    const rr = mesialSide ? roundM : roundD;
    let h = 1.0 * gauss((w - 0.10) ** 2, 0.10) * (1 - rr * Math.pow(Math.abs(u), 5.5));
    h += 0.05 * Math.cos(3 * Math.PI * u) * gauss((w - 0.10) ** 2, 0.055);
    h -= 0.28 * gauss((w + 0.45) ** 2, 0.15);                        // fosa lingual
    // Cíngulo desplazado hacia distal, como en el diente real
    h += 0.32 * gauss((w + 0.82) ** 2, 0.065) * (1 - 0.6 * (u + 0.18 * ms) ** 2);
    return Math.max(h, 0.02);
  };
}

/* ── Color por vértice ───────────────────────────────────────────────
   Una sola función continua para toda la pieza, parametrizada por la
   posición a lo largo del eje: t = -1 en el ápice, 0 en el cuello, +1 en
   oclusal. Antes había dos funciones distintas —una de corona y otra de
   raíz— y el salto entre ambas dibujaba un anillo en el cuello.

   El esmalte no es blanco plano: el borde incisal es más translúcido y
   frío, el tercio medio marfil y el cuello más saturado porque el
   esmalte adelgaza y transparenta la dentina. La raíz es cemento, más
   apagado y cálido. Los valores se quedan cerca de 1 porque el material
   los MULTIPLICA por su color, que es el que lleva el estado clínico. */
function shadeAxial(t) {
  if (t >= 0) {
    const cervical = Math.pow(1 - t, 1.5);          // cuello: más dentina
    const incisal = Math.pow(t, 2.8);               // borde: más translúcido
    return [
      1.00 - 0.11 * cervical - 0.035 * incisal,
      0.985 - 0.16 * cervical - 0.020 * incisal,
      0.945 - 0.26 * cervical + 0.025 * incisal,
    ];
  }
  /* Bajo el cuello se entra en cemento con una transición suave: la
     mezcla arranca en el mismo valor que la corona en t = 0. */
  const k = Math.min(1, Math.pow(-t, 0.75));
  const c0 = [0.890, 0.825, 0.685];                 // corona en t = 0
  const c1 = [0.800, 0.700, 0.605];                 // cemento apical
  return [
    c0[0] + (c1[0] - c0[0]) * k,
    c0[1] + (c1[1] - c0[1]) * k,
    c0[2] + (c1[2] - c0[2]) * k,
  ];
}

/**
 * Construye la malla de una pieza dental completa (corona + raíces).
 * Devuelve una BufferGeometry INDEXADA con posición, normal, uv y color.
 */
export function buildToothGeometry(THREE, code) {
  const fam = toothFamily(code);
  const [mw, bl, ch, rh] = dims(code);
  const nRoots = rootCount(code);
  const ms = mesialSign(code);
  const H = occlusalField(fam, code);
  const relief = (fam === "incisivo" ? 0.12 : 0.21) * ch;

  const pos = [], nor = [], uvs = [], col = [], idx = [];
  /* Índice del primer vértice de cada anillo. Hace falta anotarlos: entre
     anillo y anillo se insertan vértices sueltos (centro de la fosa,
     ápices, tapas de la furca), así que NO se puede recorrer la lista a
     saltos fijos para arreglar la costura. */
  const ringStarts = [];

  /** Añade un anillo de RADIAL+1 vértices (el último cierra la costura UV). */
  function addRing(fn, vTex, shadeFn) {
    const start = pos.length / 3;
    ringStarts.push(start);
    for (let i = 0; i <= RADIAL; i++) {
      const theta = ((i % RADIAL) / RADIAL) * Math.PI * 2;
      const [x, y, z] = fn(theta);
      pos.push(x, y, z);
      nor.push(0, 1, 0);                       // se recalculan al final
      uvs.push(i / RADIAL, vTex);
      const s = shadeFn(theta, x, y, z);
      col.push(s[0], s[1], s[2]);
    }
    return start;
  }

  /**
   * Cose dos anillos consecutivos. `flip` invierte el orden de vértices:
   * la corona se recorre hacia ARRIBA y la raíz hacia ABAJO, así que con
   * el mismo orden en ambas las caras de la raíz quedan orientadas hacia
   * dentro, el descarte de caras traseras las elimina y se abre un hueco
   * justo en el cuello.
   */
  function stitch(a, b, flip = false) {
    for (let i = 0; i < RADIAL; i++) {
      if (flip) {
        idx.push(a + i, b + i + 1, a + i + 1);
        idx.push(a + i, b + i, b + i + 1);
      } else {
        idx.push(a + i, a + i + 1, b + i + 1);
        idx.push(a + i, b + i + 1, b + i);
      }
    }
  }

  const cervical = (theta) => sectionRadius(fam, theta, mw / 2, bl / 2);

  /* Extensión real de la mesa oclusal. El campo de relieve H se define
     sobre [-1,1]×[-1,1], así que hay que normalizar con el contorno que
     de verdad tiene la cara oclusal, no con el del cuello. */
  const profTop = crownProfile(1, fam);
  const fzTop = blTaper(fam, 1);
  let rimA = 1e-6, rimB = 1e-6;
  for (let i = 0; i < RADIAL; i++) {
    const th = (i / RADIAL) * Math.PI * 2;
    const r = sectionRadius(fam, th, (mw / 2) * profTop, (bl / 2) * profTop * fzTop)
            * lobeFactor(lobeSpec(fam, isUpper(code)), th, 1)
            * cervicalRidge(fam, th, 1);
    rimA = Math.max(rimA, Math.abs(Math.cos(th) * r));
    rimB = Math.max(rimB, Math.abs(Math.sin(th) * r));
  }

  /**
   * Oclusión ambiental horneada. Las fosas y los surcos reciben menos luz
   * del entorno que las cúspides; hornearlo en el color de vértice hace
   * que las fisuras se lean como surcos reales y no cuesta nada en
   * tiempo de ejecución. `hRel` es la altura del campo oclusal.
   */
  function fissureAO(hRel) {
    /* Se oscurece el fondo de fosa, pero con moderación: llevado al
       extremo, toda la mesa oclusal —que está llena de valles— se apaga
       y la cara masticatoria se lee como un agujero negro en vez de como
       un relieve. */
    return 0.80 + 0.20 * Math.min(1, Math.max(0, hRel));
  }

  /**
   * Oclusión ambiental interproximal. Las caras mesial y distal quedan
   * enfrentadas a la pieza vecina, que les tapa buena parte del cielo, y
   * la tronera cervical es la zona más cerrada de todas. Sin este
   * oscurecimiento las coronas contiguas se funden en una masa blanca
   * continua y la arcada pierde la lectura pieza a pieza. Se hornea en el
   * color de vértice, así que no cuesta nada al dibujar.
   */
  function proximalAO(theta, v) {
    const prox = Math.pow(Math.abs(Math.cos(theta)), 3);
    return 1 - 0.28 * prox * (1 - 0.5 * v);
  }

  /** Color de un punto de la corona a altura v con relieve hRel. */
  function crownShade(v, hRel, theta) {
    const s = shadeAxial(v);
    let ao = hRel === null ? 1 : fissureAO(hRel);
    if (theta !== undefined) ao *= proximalAO(theta, v);
    return [s[0] * ao, s[1] * ao, s[2] * ao];
  }

  // ── Corona ──
  const lobes = lobeSpec(fam, isUpper(code));

  function crownRing(v) {
    const prof = crownProfile(v, fam);
    const fz = blTaper(fam, v);
    return (theta) => {
      // Los semiejes se escalan por separado: el mesio-distal conserva el
      // ancho y el vestíbulo-lingual se achata hacia el borde.
      const r = sectionRadius(fam, theta, (mw / 2) * prof, (bl / 2) * prof * fz)
              * lobeFactor(lobes, theta, v)
              * cervicalRidge(fam, theta, v);
      const x = Math.cos(theta) * r;
      const z = Math.sin(theta) * r;
      const blend = v > 0.74 ? (v - 0.74) / 0.26 : 0;
      const y = cejScallop(theta, ch) * (1 - v) + v * ch
              + blend * H(x / rimA, z / rimB) * relief;
      return [x, y, z];
    };
  }

  const crownStarts = [];
  for (let k = 0; k <= CROWN_RINGS; k++) {
    const v = clustered(k, CROWN_RINGS);
    const fn = crownRing(v);
    crownStarts.push(addRing(fn, 0.35 + 0.65 * v, (theta) => {
      const [x, , z] = fn(theta);
      // El sombreado por surcos solo tiene sentido cerca de la cara oclusal
      const hRel = v > 0.86 ? H(x / rimA, z / rimB) : null;
      return crownShade(v, hRel, theta);
    }));
  }
  for (let k = 0; k < CROWN_RINGS; k++) stitch(crownStarts[k], crownStarts[k + 1]);

  /* ── Mesa oclusal ──
     Disco radial que reutiliza el contorno del último anillo escalado
     hacia el centro; la altura la da el campo H, así que aparecen
     cúspides, fosa central y surcos en vez de una tapa. */
  const rimFn = crownRing(1);
  let prevCap = crownStarts[CROWN_RINGS];
  for (let k = 1; k <= CAP_RINGS; k++) {
    const r = 1 - clustered(k, CAP_RINGS);
    const fn = (theta) => {
      const [rx, , rz] = rimFn(theta);
      const x = rx * r, z = rz * r;
      return [x, ch + H(x / rimA, z / rimB) * relief, z];
    };
    const start = addRing(fn, 1, (theta) => {
      const [x, , z] = fn(theta);
      return crownShade(1, H(x / rimA, z / rimB), theta);
    });
    stitch(prevCap, start);
    prevCap = start;
  }
  // Vértice central de la fosa: cierra el disco
  {
    const c = pos.length / 3;
    const s = crownShade(1, H(0, 0));
    pos.push(0, ch + H(0, 0) * relief, 0);
    nor.push(0, 1, 0); uvs.push(0.5, 1); col.push(s[0], s[1], s[2]);
    for (let i = 0; i < RADIAL; i++) idx.push(prevCap + i, prevCap + i + 1, c);
  }

  /* ── Raíces ──
     Una sola raíz continúa el tronco sin costura. Con dos o tres, el
     tronco baja hasta la furca, se cierra, y cada raíz nace dentro de él:
     piezas cerradas que se interpenetran, nunca un agujero. */
  /* Curvatura radicular por familia. Casi ninguna raíz es recta: se
     inclinan a distal y el tercio apical acentúa el giro. */
  const rootCurve = { incisivo: 0.09, canino: 0.11, premolar: 0.13, molar: 0.16 }[fam];

  /**
   * Concavidades longitudinales de la raíz. Las caras mesial y distal de
   * casi todas las raíces están acanaladas —muy marcado en el primer
   * premolar superior y en las raíces de los molares—, y es lo que
   * distingue una raíz de un cono liso. La acanaladura es máxima en el
   * tercio medio y se cierra hacia el ápice.
   */
  function rootGroove(theta, v, depth) {
    const prox = Math.pow(Math.abs(Math.cos(theta)), 2);
    const band = Math.exp(-((v - 0.42) ** 2) / 0.14);
    return 1 - depth * prox * band;
  }
  const grooveDepth = fam === "premolar" ? 0.20 : fam === "molar" ? 0.16 : 0.10;

  /* Torsión radicular: la sección gira poco a poco alrededor del eje al
     descender. Es sutil pero rompe el aspecto de extrusión recta, que es
     lo que hace que una raíz parezca torneada a máquina. */
  const rootTwist = { incisivo: 0.16, canino: 0.20, premolar: 0.26, molar: 0.30 }[fam];

  /* La sección cambia de forma con la profundidad: ovalada en el cuello
     y progresivamente más aplanada en sentido mesio-distal hacia el
     ápice, sobre todo en premolares y raíces de molares. */
  const rootFlatten = { incisivo: 0.10, canino: 0.14, premolar: 0.26, molar: 0.22 }[fam];

  function rootRing(v, ox, oz, thick, len) {
    return (theta) => {
      const taper = rootProfile(v);
      // Torsión y aplanamiento progresivos de la sección
      const th = theta + rootTwist * v * v * ms;
      const flat = 1 - rootFlatten * v * Math.pow(Math.abs(Math.cos(th)), 2);
      const r = cervical(th) * taper * thick * flat * rootGroove(th, v, grooveDepth);
      // La curvatura se acelera hacia el ápice, no crece de forma lineal
      const bend = rootCurve * mw * Math.pow(v, 1.8) * ms;
      return [
        Math.cos(theta) * r + ox * v + bend,
        -v * len + cejScallop(theta, ch) * (1 - Math.min(1, v * 3)),
        Math.sin(theta) * r + oz * v,
      ];
    };
  }

  const rootShade = (v) => (theta) => {
    const s = shadeAxial(-v);
    const ao = 1 - 0.24 * Math.pow(Math.abs(Math.cos(theta)), 3) * (1 - v);
    return [s[0] * ao, s[1] * ao, s[2] * ao];
  };

  function buildRoot(fromRing, ox, oz, thick, len, vStart) {
    let prev = fromRing;
    for (let k = 1; k <= ROOT_RINGS; k++) {
      const v = vStart + (1 - vStart) * clustered(k, ROOT_RINGS);
      const start = addRing(rootRing(v, ox, oz, thick, len), 0.35 * (1 - v), rootShade(v));
      stitch(prev, start, true);
      prev = start;
    }
    const apex = pos.length / 3;
    const s = shadeAxial(-1);
    pos.push(ox + 0.10 * mw, -len * 1.03, oz);
    nor.push(0, -1, 0); uvs.push(0.5, 0); col.push(s[0], s[1], s[2]);
    for (let i = 0; i < RADIAL; i++) idx.push(prev + i + 1, prev + i, apex);
  }

  if (nRoots === 1) {
    buildRoot(crownStarts[0], 0, 0, 1, rh, 0);
  } else {
    const furca = 0.30;
    let prev = crownStarts[0];
    for (let k = 1; k <= 3; k++) {
      const v = (furca * k) / 3;
      const start = addRing(rootRing(v, 0, 0, 1, rh), 0.35 * (1 - v), rootShade(v));
      stitch(prev, start, true);
      prev = start;
    }
    // Tapa de la furca (queda dentro de la encía, nunca a la vista)
    {
      const c = pos.length / 3;
      const s = shadeAxial(-furca);
      const f = rootRing(furca, 0, 0, 1, rh)(0);
      pos.push(0, f[1], 0);
      nor.push(0, -1, 0); uvs.push(0.5, 0); col.push(s[0], s[1], s[2]);
      for (let i = 0; i < RADIAL; i++) idx.push(prev + i + 1, prev + i, c);
    }
    /* Divergencia real entre raíces: no son dos copias simétricas. En el
       molar inferior la mesial es más ancha, más larga y se curva más que
       la distal; en el superior la palatina es la mayor y las
       vestibulares divergen menos entre sí. */
    const specs = nRoots === 2
      ? [{ ox: -mw * 0.38 * ms, oz: 0, thick: 0.66, len: rh * 1.04 },   // mesial
         { ox: mw * 0.30 * ms, oz: 0, thick: 0.56, len: rh * 0.94 }]    // distal
      : [{ ox: -mw * 0.34 * ms, oz: bl * 0.28, thick: 0.54, len: rh * 0.92 },
         { ox: mw * 0.26 * ms, oz: bl * 0.24, thick: 0.48, len: rh * 0.86 },
         { ox: 0.04 * mw * ms, oz: -bl * 0.32, thick: 0.64, len: rh * 1.06 }];
    for (const sp of specs) {
      const startRing = addRing(rootRing(furca, sp.ox, sp.oz, sp.thick, sp.len),
                                0.35 * (1 - furca), rootShade(furca));
      buildRoot(startRing, sp.ox, sp.oz, sp.thick, sp.len, furca);
      // Tapa superior de la raíz, dentro del tronco
      const c = pos.length / 3;
      const s = shadeAxial(-furca);
      const f = rootRing(furca, sp.ox, sp.oz, sp.thick, sp.len)(0);
      pos.push(sp.ox * furca, f[1], sp.oz * furca);
      nor.push(0, 1, 0); uvs.push(0.5, 0.5); col.push(s[0], s[1], s[2]);
      for (let i = 0; i < RADIAL; i++) idx.push(startRing + i, startRing + i + 1, c);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setIndex(idx);
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("normal", new THREE.Float32BufferAttribute(nor, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  geo.computeVertexNormals();

  /* Costura: los vértices duplicados de θ=0 y θ=2π ocupan el mismo punto
     pero reciben normales distintas (cada uno ve solo sus caras), lo que
     dibujaría una línea de luz. Se promedian para que desaparezca. */
  const nAttr = geo.attributes.normal;
  for (const base of ringStarts) {
    const a = base, b = base + RADIAL;
    const nx = nAttr.getX(a) + nAttr.getX(b);
    const ny = nAttr.getY(a) + nAttr.getY(b);
    const nz = nAttr.getZ(a) + nAttr.getZ(b);
    const len = Math.hypot(nx, ny, nz) || 1;
    nAttr.setXYZ(a, nx / len, ny / len, nz / len);
    nAttr.setXYZ(b, nx / len, ny / len, nz / len);
  }
  nAttr.needsUpdate = true;
  geo.computeBoundingSphere();
  return geo;
}

/**
 * Geometría reutilizable: piezas con la misma familia, dentición, número
 * de raíces y variante oclusal comparten malla. Es lo que permite
 * mantener la fluidez en tablet con las arcadas completas. El caché lo
 * aporta y lo libera quien construye la escena.
 */
export function toothGeometryKey(code) {
  /* El lado entra en la clave: las coronas son asimétricas en sentido
     mesio-distal, así que la pieza derecha y la izquierda del mismo
     número son mallas distintas (imágenes especulares). Pasa de unas
     doce mallas únicas a unas veinticuatro, cifra que sigue siendo
     irrelevante frente a las 52 piezas de la boca. */
  return `${toothFamily(code)}|${isDeciduous(code) ? "d" : "p"}`
       + `|${rootCount(code)}|${occlusalVariant(code)}|${mesialSign(code)}`;
}

export function getToothGeometry(THREE, code, cache) {
  const key = toothGeometryKey(code);
  let geo = cache.get(key);
  if (!geo) {
    geo = buildToothGeometry(THREE, code);
    cache.set(key, geo);
  }
  return geo;
}

/** Medidas útiles para colocar la pieza en la arcada. */
export function toothMetrics(code) {
  const [mw, bl, ch, rh] = dims(code);
  const [sx, sy, sz] = toothScale(code);
  return { mdWidth: mw * sx, blDepth: bl * sz, crownH: ch * sy, rootH: rh * sy };
}

/** Altura total aproximada. */
export function toothHeight(code) {
  const { crownH, rootH } = toothMetrics(code);
  return crownH + rootH;
}
