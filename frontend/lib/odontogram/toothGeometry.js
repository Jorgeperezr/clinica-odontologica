"use client";

/**
 * Geometría dental anatómica (Sprint 49 · refinada en Sprint 53).
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
 * lado vestibular. Gracias a eso la geometría solo depende de (familia,
 * temporal, nº de raíces) y se puede **reutilizar** entre piezas
 * equivalentes: de 52 mallas únicas se pasa a unas diez.
 *
 * ANATOMÍA QUE SE MODELA
 *
 *   · Sección transversal por familia (superelipse): el molar tiende al
 *     cuadrado redondeado, el incisivo es una lámina aplanada.
 *   · Perfil vertical real: ecuador en el tercio medio, constricción
 *     cervical y raíces que afinan hasta el ápice con curvatura distal.
 *   · Cara oclusal con relieve verdadero —cúspides, fosa central, surcos
 *     de desarrollo y rebordes marginales— resuelta como un campo de
 *     altura H(u,w) sobre el plano oclusal, no como una tapa plana.
 *   · Unión amelocementaria festoneada y color de vértice que pasa de
 *     esmalte translúcido a dentina y cemento.
 *
 * GARANTÍA DE ESTANQUEIDAD
 * Cada parte (corona+tronco, cada raíz) es una superficie CERRADA con
 * sus tapas. Los agujeros negros que se veían antes venían de coser dos
 * lofts de radios distintos en el cuello; ahora corona y raíz comparten
 * por construcción el mismo anillo cervical, y las raíces múltiples
 * nacen dentro del tronco, ya cerrado.
 *
 * COSTE
 * ~1.300 triángulos por pieza en malla INDEXADA (un tercio de la memoria
 * de la versión no indexada anterior), compartida entre piezas iguales.
 */

import { toothFamily, isUpper } from "./ToothArt";

const RADIAL = 26;        // secciones alrededor del eje
const CROWN_RINGS = 10;   // anillos de la corona
const CAP_RINGS = 4;      // anillos de la mesa oclusal
const ROOT_RINGS = 8;     // anillos de cada raíz (van dentro de la encía)

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
   10,5 de corona: relación ≈ 1,24). Con relaciones más esbeltas las
   piezas se leen como colmillos, que es lo que pasaba antes. */
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
 * Ajuste fino por pieza concreta dentro de su familia. Un incisivo
 * lateral es más estrecho que un central y un segundo molar menor que un
 * primero; sin esto todas las piezas de una familia se ven clonadas.
 * Se aplica como escala del objeto, no de la malla, para no romper la
 * reutilización de geometría.
 */
export function toothScale(code) {
  const n = Number(String(code).slice(-1));
  const fam = toothFamily(code);
  const up = isUpper(code);
  if (fam === "incisivo") {
    // Los incisivos inferiores son las piezas más estrechas de la boca;
    // el lateral superior, algo menor que el central.
    if (up) return n === 2 ? [0.86, 0.92, 0.95] : [1, 1, 1];
    return n === 1 ? [0.66, 0.86, 0.82] : [0.74, 0.90, 0.84];
  }
  if (fam === "canino") return up ? [1, 1, 1] : [0.94, 0.97, 0.96];
  if (fam === "premolar") return n === 5 ? [0.96, 0.97, 1.0] : [1, 1, 1];
  if (fam === "molar") {
    if (n === 7) return [0.93, 0.95, 0.96];
    if (n === 8) return [0.84, 0.88, 0.92];   // el cordal es menor y más irregular
  }
  return [1, 1, 1];
}

/* ── Sección transversal ─────────────────────────────────────────────
   Superelipse: el exponente controla cuánto se parece al cuadrado. El
   molar es casi rectangular con esquinas redondeadas; el incisivo, una
   lámina. Se añade la concavidad lingual y las convexidades proximales
   (áreas de contacto), que son las que hacen que dos piezas vecinas se
   toquen de forma creíble. */
function sectionRadius(fam, theta, a, b) {
  const n = { molar: 3.4, premolar: 2.8, canino: 2.3, incisivo: 2.15 }[fam];
  const ct = Math.cos(theta), st = Math.sin(theta);
  // Radio de la superelipse en la dirección theta (x = a·cosθ, z = b·sinθ)
  const denom = Math.pow(
    Math.pow(Math.abs(ct) / a, n) + Math.pow(Math.abs(st) / b, n),
    -1 / n,
  );
  let r = denom;

  // Concavidad lingual (z < 0) más marcada en incisivos y caninos
  if (st < 0) {
    const k = fam === "incisivo" ? 0.16 : fam === "canino" ? 0.12 : 0.05;
    r *= 1 - k * st * st;
  }
  // Convexidad proximal: refuerza el punto de contacto mesial y distal
  r *= 1 + 0.035 * ct * ct;
  return r;
}

/**
 * Perfil vertical de la corona. v = 0 en el cuello, 1 en el borde
 * oclusal. Ecuador en el tercio medio y cierre suave hacia oclusal.
 * El incisivo apenas se recoge: su borde incisal conserva casi todo el
 * ancho mesio-distal, y recortarlo es lo que lo convertía en un cono.
 */
function crownProfile(v, fam) {
  const eq = fam === "molar" ? 0.40 : 0.46;          // altura del ecuador
  const bulge = fam === "incisivo" ? 0.12 : 0.20;    // cuánto sobresale
  const close = fam === "incisivo" ? 0.07 : fam === "canino" ? 0.14 : 0.20;
  if (v <= eq) {
    /* Del cuello al ecuador. La curva arranca con pendiente CERO
       (smoothstep en vez de seno): si el diámetro crece de golpe al
       salir del cuello, la unión con la raíz forma una arista viva que
       se lee como una grieta iluminada alrededor de toda la pieza. */
    const t = v / eq;
    return 1 + bulge * (t * t * (3 - 2 * t));
  }
  // Del ecuador a oclusal: recogida progresiva
  const x = (v - eq) / (1 - eq);
  return 1 + bulge * (1 - x * x) - close * x * x;
}

/**
 * Achatamiento vestíbulo-lingual hacia el borde oclusal. Es la clave de
 * la forma del incisivo: la corona nace gruesa en el cuello y termina en
 * una LÁMINA. Sin esto, la sección se mantiene casi circular arriba y la
 * tapa oclusal se cierra en punta, que es de donde salía el aspecto de
 * colmillo. Los molares apenas se achatan: su mesa es ancha.
 */
function blTaper(fam, v) {
  const end = { incisivo: 0.40, canino: 0.70, premolar: 0.88, molar: 0.93 }[fam];
  return 1 - (1 - end) * Math.pow(v, 1.4);
}

/**
 * Perfil de la raíz. v = 0 en el cuello, 1 en el ápice. Estrechamiento
 * continuo con ligera curvatura distal, como una raíz real.
 */
function rootProfile(v) {
  // Arranca también con pendiente casi nula en el cuello (mismo motivo
  // que en la corona) y afina como una raíz real hacia el ápice.
  return Math.pow(Math.max(0, 1 - v * v), 0.5) * 0.94 + 0.06 * (1 - v);
}

/**
 * Festón de la unión amelocementaria: el cuello sube en mesial y distal
 * y baja en vestibular y lingual. Es un detalle pequeño que evita el
 * aspecto de "tubo cortado a máquina" en la zona del cuello.
 */
function cejScallop(theta, ch) {
  return Math.cos(2 * theta) * ch * 0.045;
}

/* ── Cara oclusal ────────────────────────────────────────────────────
   Campo de altura H(u, w) sobre el plano oclusal, con u = x/(ancho/2) y
   w = z/(profundidad/2), ambos en [-1, 1]. Devuelve altura relativa
   (0 = fondo de fosa, 1 = punta de cúspide). Modelar la cara oclusal
   como campo y no como tapa es lo que produce cúspides, fosas y surcos
   de verdad. */
function gauss(d2, k) {
  return Math.exp(-d2 / k);
}

function occlusalField(fam, code) {
  const n = Number(String(code).slice(-1));
  const up = isUpper(code);

  if (fam === "molar") {
    // Cuatro cúspides (MV, DV, ML, DL). El primer molar inferior suma
    // la distal, y el superior tiene la mesiolingual dominante unida a
    // la distovestibular por la cresta oblicua.
    const cusps = [
      { u: -0.52, w: 0.52, a: 1.00 },   // mesiovestibular
      { u: 0.50, w: 0.50, a: 0.94 },    // distovestibular
      { u: -0.50, w: -0.52, a: up ? 1.02 : 0.92 }, // mesiolingual
      { u: 0.50, w: -0.50, a: 0.88 },   // distolingual
    ];
    if (!up && n === 6) cusps.push({ u: 0.80, w: 0.06, a: 0.80 }); // distal del 1er molar inferior
    return (u, w) => {
      let h = 0;
      for (const c of cusps) {
        h += c.a * gauss((u - c.u) ** 2 + (w - c.w) ** 2, 0.30);
      }
      // Rebordes marginales mesial y distal
      h += 0.42 * gauss((Math.abs(u) - 0.86) ** 2, 0.045) * (1 - 0.5 * w * w);
      // Surcos de desarrollo en cruz
      h -= 0.30 * gauss(u * u, 0.020);
      h -= 0.26 * gauss(w * w, 0.020);
      // Cresta oblicua del molar superior: une MV con DL
      if (up) h += 0.20 * gauss((u * 0.7 + w * 0.7) ** 2, 0.05);
      return h;
    };
  }

  if (fam === "premolar") {
    // Dos cúspides enfrentadas, la vestibular más alta, con surco
    // central mesio-distal y rebordes marginales.
    return (u, w) => {
      let h = 1.00 * gauss(u * u * 0.55 + (w - 0.56) ** 2, 0.34);   // vestibular
      h += 0.86 * gauss(u * u * 0.55 + (w + 0.54) ** 2, 0.30);      // lingual
      h += 0.40 * gauss((Math.abs(u) - 0.82) ** 2, 0.040) * (1 - 0.6 * w * w);
      h -= 0.34 * gauss(w * w, 0.022);                              // surco central
      return h;
    };
  }

  if (fam === "canino") {
    // Cúspide única desplazada a mesial, con sus dos vertientes y el
    // cíngulo lingual.
    return (u, w) => {
      let h = 1.05 * gauss((u + 0.06) ** 2 * 0.9 + (w - 0.05) ** 2 * 0.7, 0.34);
      h += 0.30 * gauss((w + 0.72) ** 2, 0.10) * (1 - 0.7 * u * u);  // cíngulo
      h -= 0.18 * gauss((w + 0.36) ** 2, 0.05);                      // fosa lingual
      return Math.max(h, 0.04);
    };
  }

  /* Incisivo: borde incisal en lámina, fosa lingual y cíngulo. La
     campana en `w` es ESTRECHA a propósito: así la altura se mantiene a
     lo largo de todo el eje mesio-distal y cae de golpe hacia vestibular
     y lingual, que es lo que produce una arista recta —un cincel— en vez
     de una cúpula. Los mamelones se insinúan apenas, como en un diente
     joven. */
  return (u, w) => {
    let h = 1.0 * gauss((w - 0.10) ** 2, 0.11) * (1 - 0.16 * Math.pow(u, 6));
    h += 0.05 * Math.cos(3 * Math.PI * u) * gauss((w - 0.10) ** 2, 0.06);
    h -= 0.26 * gauss((w + 0.45) ** 2, 0.16);                        // fosa lingual
    h += 0.30 * gauss((w + 0.82) ** 2, 0.07) * (1 - 0.6 * u * u);    // cíngulo
    return Math.max(h, 0.02);
  };
}

/* ── Color por vértice ───────────────────────────────────────────────
   El esmalte no es blanco plano: el borde incisal es más translúcido y
   frío, el tercio medio marfil y el cuello más saturado porque el
   esmalte adelgaza y transparenta la dentina. La raíz es cemento, más
   apagado y cálido. Los valores se quedan cerca de 1 porque el material
   los MULTIPLICA por su color, que es el que lleva el estado clínico. */
function shadeAt(yFrac, isRoot) {
  if (isRoot) {
    // yFrac: 0 en el cuello, 1 en el ápice
    const t = Math.min(1, yFrac * 1.2);
    return [0.92 - 0.12 * t, 0.84 - 0.14 * t, 0.74 - 0.13 * t];
  }
  /* yFrac: 0 en el cuello, 1 en oclusal. El marfil se marca más que en
     la primera versión: con variaciones de un 5 % el diente se leía como
     un blanco plano de laboratorio. */
  const cervical = Math.pow(1 - yFrac, 1.6);      // cuello: más dentina
  const incisal = Math.pow(yFrac, 2.6);           // borde: más translúcido
  return [
    1.00 - 0.10 * cervical - 0.03 * incisal,
    0.985 - 0.15 * cervical - 0.015 * incisal,
    0.945 - 0.24 * cervical + 0.020 * incisal,
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
  const H = occlusalField(fam, code);
  const relief = (fam === "incisivo" ? 0.11 : 0.19) * ch;

  const pos = [], nor = [], uvs = [], col = [], idx = [];
  /* Índice del primer vértice de cada anillo. Hace falta anotarlos: entre
     anillo y anillo se insertan vértices sueltos (centro de la fosa,
     ápices, tapas de la furca), así que NO se puede recorrer la lista a
     saltos fijos para arreglar la costura. */
  const ringStarts = [];

  /** Añade un anillo de RADIAL+1 vértices (el último cierra la costura UV). */
  function addRing(fn, vTex, shade) {
    const start = pos.length / 3;
    ringStarts.push(start);
    for (let i = 0; i <= RADIAL; i++) {
      const theta = (i % RADIAL) / RADIAL * Math.PI * 2;
      const [x, y, z] = fn(theta);
      pos.push(x, y, z);
      nor.push(0, 1, 0);                       // se recalculan al final
      uvs.push(i / RADIAL, vTex);
      col.push(shade[0], shade[1], shade[2]);
    }
    return start;
  }

  /**
   * Cose dos anillos consecutivos.
   *
   * `flip` invierte el orden de los vértices. Hace falta porque la corona
   * se recorre hacia ARRIBA y la raíz hacia ABAJO: con el mismo orden en
   * ambas, las caras de la raíz quedan orientadas hacia dentro, el
   * descarte de caras traseras las elimina y se abre un hueco justo en el
   * cuello (por el que se veía el interior de la pieza).
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

  /* ── Corona ──
     El anillo cervical (v = 0) se calcula con la MISMA función que usa
     la raíz, de modo que ambos coinciden vértice a vértice y la unión
     es estanca por construcción. */
  const cervical = (theta) => sectionRadius(fam, theta, mw / 2, bl / 2);

  /* Extensión real de la mesa oclusal. El campo de relieve H se define
     sobre [-1,1] × [-1,1], así que hay que normalizar con el contorno
     que de verdad tiene la cara oclusal —no con el del cuello— o el
     relieve se aplicaría a una escala equivocada. */
  const profTop = crownProfile(1, fam);
  const fzTop = blTaper(fam, 1);
  let rimA = 1e-6, rimB = 1e-6;
  for (let i = 0; i < RADIAL; i++) {
    const th = (i / RADIAL) * Math.PI * 2;
    const r = sectionRadius(fam, th, (mw / 2) * profTop, (bl / 2) * profTop * fzTop);
    rimA = Math.max(rimA, Math.abs(Math.cos(th) * r));
    rimB = Math.max(rimB, Math.abs(Math.sin(th) * r));
  }

  function crownRing(v) {
    const prof = crownProfile(v, fam);
    const fz = blTaper(fam, v);
    return (theta) => {
      // Los semiejes se escalan por separado: el mesio-distal conserva
      // el ancho y el vestíbulo-lingual se achata hacia el borde.
      const r = sectionRadius(fam, theta, (mw / 2) * prof, (bl / 2) * prof * fz);
      const x = Math.cos(theta) * r;
      const z = Math.sin(theta) * r;
      // Altura: sube por la corona y, cerca de oclusal, adopta el relieve
      const blend = v > 0.78 ? (v - 0.78) / 0.22 : 0;
      const y = cejScallop(theta, ch) * (1 - v) + v * ch
              + blend * H(x / rimA, z / rimB) * relief;
      return [x, y, z];
    };
  }

  const crownStarts = [];
  for (let k = 0; k <= CROWN_RINGS; k++) {
    const v = k / CROWN_RINGS;
    crownStarts.push(addRing(crownRing(v), 0.35 + 0.65 * v, shadeAt(v, false)));
  }
  for (let k = 0; k < CROWN_RINGS; k++) stitch(crownStarts[k], crownStarts[k + 1]);

  /* ── Mesa oclusal ──
     Disco radial que reutiliza el contorno del último anillo escalado
     hacia el centro; la altura la da el campo H, así que aparecen
     cúspides, fosa central y surcos en vez de una tapa. */
  const rimFn = crownRing(1);
  let prevCap = crownStarts[CROWN_RINGS];
  for (let k = 1; k <= CAP_RINGS; k++) {
    const r = 1 - k / CAP_RINGS;
    const shade = shadeAt(1, false);
    const start = addRing((theta) => {
      const [rx, , rz] = rimFn(theta);
      const x = rx * r, z = rz * r;
      return [x, ch + H(x / rimA, z / rimB) * relief, z];
    }, 1, shade);
    stitch(prevCap, start);
    prevCap = start;
  }
  // Vértice central de la fosa: cierra el disco
  {
    const c = pos.length / 3;
    const s = shadeAt(1, false);
    pos.push(0, ch + H(0, 0) * relief, 0);
    nor.push(0, 1, 0); uvs.push(0.5, 1); col.push(s[0], s[1], s[2]);
    for (let i = 0; i < RADIAL; i++) idx.push(prevCap + i, prevCap + i + 1, c);
  }

  /* ── Raíces ──
     Una sola raíz continúa el tronco sin costura. Con dos o tres, el
     tronco baja hasta la furca, se cierra, y cada raíz nace dentro de
     él: piezas cerradas que se interpenetran, nunca un agujero. */
  function rootRing(v, ox, oz, thick, len) {
    return (theta) => {
      const taper = rootProfile(v);
      const r = cervical(theta) * taper * thick;
      // Curvatura distal progresiva de la raíz
      const bend = 0.10 * mw * v * v;
      return [
        Math.cos(theta) * r + ox * v + bend,
        -v * len + cejScallop(theta, ch) * (1 - Math.min(1, v * 3)),
        Math.sin(theta) * r + oz * v,
      ];
    };
  }

  function buildRoot(fromRing, ox, oz, thick, len, vStart) {
    let prev = fromRing;
    for (let k = 1; k <= ROOT_RINGS; k++) {
      const v = vStart + (1 - vStart) * (k / ROOT_RINGS);
      const start = addRing(rootRing(v, ox, oz, thick, len), 0.35 * (1 - v),
                            shadeAt(v, true));
      stitch(prev, start, true);
      prev = start;
    }
    // Ápice: cierre en punta
    const apex = pos.length / 3;
    const s = shadeAt(1, true);
    pos.push(ox + 0.10 * mw, -len * 1.03, oz);
    nor.push(0, -1, 0); uvs.push(0.5, 0); col.push(s[0], s[1], s[2]);
    for (let i = 0; i < RADIAL; i++) idx.push(prev + i + 1, prev + i, apex);
  }

  if (nRoots === 1) {
    buildRoot(crownStarts[0], 0, 0, 1, rh, 0);
  } else {
    // Tronco común hasta la furca
    const furca = 0.30;
    let prev = crownStarts[0];
    for (let k = 1; k <= 3; k++) {
      const v = (furca * k) / 3;
      const start = addRing(rootRing(v, 0, 0, 1, rh), 0.35 * (1 - v), shadeAt(v, true));
      stitch(prev, start, true);
      prev = start;
    }
    // Tapa de la furca (queda dentro de la encía, nunca a la vista)
    {
      const c = pos.length / 3;
      const s = shadeAt(furca, true);
      const f = rootRing(furca, 0, 0, 1, rh)(0);
      pos.push(0, f[1], 0);
      nor.push(0, -1, 0); uvs.push(0.5, 0); col.push(s[0], s[1], s[2]);
      for (let i = 0; i < RADIAL; i++) idx.push(prev + i + 1, prev + i, c);
    }
    const specs = nRoots === 2
      ? [{ ox: -mw * 0.34, oz: 0, thick: 0.60, len: rh },
         { ox: mw * 0.34, oz: 0, thick: 0.60, len: rh }]
      : [{ ox: -mw * 0.30, oz: bl * 0.26, thick: 0.52, len: rh * 0.90 },
         { ox: mw * 0.30, oz: bl * 0.26, thick: 0.52, len: rh * 0.90 },
         { ox: 0, oz: -bl * 0.30, thick: 0.60, len: rh }];
    for (const sp of specs) {
      // Cada raíz arranca con su propio anillo a la altura de la furca
      const startRing = addRing(rootRing(furca, sp.ox, sp.oz, sp.thick, sp.len),
                                0.35 * (1 - furca), shadeAt(furca, true));
      buildRoot(startRing, sp.ox, sp.oz, sp.thick, sp.len, furca);
      // Tapa superior de la raíz, dentro del tronco
      const c = pos.length / 3;
      const s = shadeAt(furca, true);
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
 * Geometría reutilizable: piezas con la misma familia, dentición y
 * número de raíces comparten malla. Reduce de 52 mallas a unas diez, que
 * es lo que permite mantener 60 fps en tablet con las arcadas completas.
 * El caché lo aporta y lo libera quien construye la escena.
 */
export function toothGeometryKey(code) {
  return `${toothFamily(code)}|${isDeciduous(code) ? "d" : "p"}|${rootCount(code)}`;
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
