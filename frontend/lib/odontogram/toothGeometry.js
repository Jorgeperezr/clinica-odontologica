"use client";

/**
 * Geometría dental anatómica (Sprint 49).
 * ────────────────────────────────────────────────────────────────────
 * Sustituye las cajas del sprint anterior por mallas generadas mediante
 * "lofting": se apilan secciones transversales a lo largo del eje del
 * diente y se cosen en una superficie continua con normales suavizadas.
 *
 * La forma de cada sección se controla con dos funciones:
 *
 *   radio(θ, t)  → el contorno horizontal a la altura t. Modulado por
 *                  lóbulos, produce las cúspides: cuatro en un molar,
 *                  dos en un premolar, una en un canino, y un perfil
 *                  aplanado vestíbulo-palatino en un incisivo.
 *
 *   altura(θ, t) → permite que el borde oclusal suba y baje según el
 *                  ángulo, que es lo que da relieve real a las cúspides
 *                  en lugar de una tapa plana.
 *
 * El perfil vertical reproduce la anatomía: ecuador marcado en el tercio
 * medio de la corona, constricción en el cuello y raíces que afinan
 * hasta el ápice. Las piezas temporales son más bulbosas y de raíz corta.
 *
 * Coste: ~28 × 26 vértices por pieza (unos 1.400 triángulos), suficiente
 * para que las curvas se lean suaves y ligero para mantener 60 fps con
 * las dos arcadas completas en pantalla.
 */

import { toothFamily, isUpper } from "./ToothArt";

const RADIAL = 28;   // secciones alrededor del eje
const RINGS = 26;    // secciones a lo largo del eje

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

/** Dimensiones base: [ancho mesio-distal, profundidad vestíbulo-lingual, alto corona, alto raíz] */
function dims(code) {
  const fam = toothFamily(code);
  const dec = isDeciduous(code);
  const s = dec ? 0.76 : 1;
  const base = {
    incisivo: [0.58, 0.40, 1.05, 1.35],
    canino: [0.60, 0.55, 1.25, 1.65],
    premolar: [0.66, 0.72, 0.95, 1.25],
    molar: [0.98, 0.92, 0.88, 1.25],
  }[fam];
  // Las temporales tienen corona proporcionalmente más ancha y raíz corta
  return [base[0] * s, base[1] * s, base[2] * s, base[3] * (dec ? 0.62 : 1)];
}

/**
 * Modulación angular del radio: crea los lóbulos que se convierten en
 * cúspides. `θ = 0` mira a vestibular.
 */
function lobeFactor(fam, theta) {
  switch (fam) {
    case "molar":
      // Cuatro cúspides: dos vestibulares y dos palatinas
      return 1 + 0.14 * Math.cos(2 * theta) + 0.07 * Math.cos(4 * theta);
    case "premolar":
      // Dos cúspides enfrentadas
      return 1 + 0.16 * Math.cos(2 * theta);
    case "canino":
      // Cúspide única, más volumen vestibular
      return 1 + 0.12 * Math.cos(theta);
    default:
      // Incisivo: sección aplanada, borde en lámina
      return 1 + 0.05 * Math.cos(2 * theta);
  }
}

/** Relieve oclusal: cuánto sube el borde según el ángulo (0 = surco, 1 = cúspide). */
function cuspHeight(fam, theta) {
  switch (fam) {
    case "molar":
      return 0.5 + 0.5 * Math.cos(2 * theta) * Math.cos(2 * theta);
    case "premolar":
      return 0.5 + 0.5 * Math.abs(Math.cos(theta));
    case "canino":
      return Math.pow(Math.max(0, Math.cos(theta * 0.9)), 2);
    default:
      return 0.85;   // borde incisal casi recto
  }
}

/**
 * Perfil vertical del cuerpo del diente.
 * t = 0 en el cuello, t = 1 en la superficie oclusal/incisal.
 * Devuelve el factor de radio (ecuador en el tercio medio).
 */
function crownProfile(t, fam) {
  // Curva suave: estrecho en cuello, máximo hacia 0.45, cierre en oclusal
  const equator = fam === "molar" ? 0.42 : 0.48;
  const bulge = fam === "incisivo" ? 0.16 : 0.24;
  const x = (t - equator) / (1 - equator);
  return 0.80 + bulge * Math.sin(Math.PI * Math.min(1, t / equator) * 0.5)
              - (t > equator ? 0.18 * x * x : 0);
}

/**
 * Construye la malla de una pieza dental completa (corona + raíces).
 * Devuelve una BufferGeometry no indexada con normales suavizadas.
 */
export function buildToothGeometry(THREE, code) {
  const fam = toothFamily(code);
  const up = isUpper(code);
  const [mw, bl, ch, rh] = dims(code);
  const nRoots = rootCount(code);

  const positions = [];

  // Sentido vertical: en superiores la corona apunta hacia abajo
  const dir = up ? -1 : 1;

  /** Punto de la superficie de la corona en (θ, t). */
  function crownPoint(theta, t) {
    const lobe = lobeFactor(fam, theta);
    const prof = crownProfile(t, fam);
    const rx = (mw / 2) * lobe * prof;
    const rz = (bl / 2) * prof * (fam === "incisivo" ? 0.82 : 1);
    // El relieve oclusal solo actúa en el extremo superior
    const relief = t > 0.86 ? (t - 0.86) / 0.14 : 0;
    const y = t * ch + relief * cuspHeight(fam, theta) * ch * 0.13;
    return [Math.cos(theta) * rz, dir * y, Math.sin(theta) * rx];
  }

  /** Punto de una raíz: se estrecha hasta el ápice y se desplaza lateralmente. */
  function rootPoint(theta, t, idx) {
    // t = 0 en el cuello, 1 en el ápice
    const taper = Math.pow(1 - t, 0.62) * 0.92;
    let ox = 0, oz = 0, len = rh, thick = 1;
    if (nRoots === 2) {
      const s = idx === 0 ? -1 : 1;
      oz = s * mw * 0.30 * t;
      thick = 0.62;
    } else if (nRoots === 3) {
      if (idx === 2) { ox = bl * 0.28 * t; thick = 0.66; }
      else {
        const s = idx === 0 ? -1 : 1;
        oz = s * mw * 0.28 * t;
        ox = -bl * 0.16 * t;
        thick = 0.54;
        len = rh * 0.88;
      }
    }
    const rx = (mw / 2) * 0.86 * taper * thick;
    const rz = (bl / 2) * 0.86 * taper * thick;
    const y = -t * len;
    return [Math.cos(theta) * rz + ox, dir * y, Math.sin(theta) * rx + oz];
  }

  /** Cose dos anillos consecutivos en dos triángulos por segmento. */
  function stitch(ringA, ringB) {
    for (let i = 0; i < RADIAL; i++) {
      const j = (i + 1) % RADIAL;
      const a = ringA[i], b = ringA[j], c = ringB[j], d = ringB[i];
      positions.push(...a, ...b, ...c);
      positions.push(...a, ...c, ...d);
    }
  }

  const ring = (fn, t, idx) => {
    const r = [];
    for (let i = 0; i < RADIAL; i++) r.push(fn((i / RADIAL) * Math.PI * 2, t, idx));
    return r;
  };

  // ── Corona ──
  let prev = ring(crownPoint, 0);
  for (let k = 1; k <= RINGS; k++) {
    const cur = ring(crownPoint, k / RINGS);
    stitch(prev, cur);
    prev = cur;
  }
  // Tapa oclusal: abanico hacia el centro elevado
  const topCenterY = dir * (ch + (fam === "incisivo" ? 0.02 : 0.05));
  for (let i = 0; i < RADIAL; i++) {
    const j = (i + 1) % RADIAL;
    positions.push(...prev[i], ...prev[j], 0, topCenterY, 0);
  }

  // ── Raíces ──
  for (let idx = 0; idx < nRoots; idx++) {
    let p = ring(rootPoint, 0, idx);
    for (let k = 1; k <= RINGS; k++) {
      const cur = ring(rootPoint, k / RINGS, idx);
      stitch(p, cur);
      p = cur;
    }
    // Ápice: cierre en punta
    const apex = rootPoint(0, 1, idx);
    for (let i = 0; i < RADIAL; i++) {
      const j = (i + 1) % RADIAL;
      positions.push(...p[j], ...p[i], apex[0] * 0.15, apex[1] * 1.04, apex[2] * 0.15);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();   // normales suavizadas: sin facetas visibles
  geo.computeBoundingSphere();
  return geo;
}

/** Altura total aproximada, útil para colocar la pieza en la arcada. */
export function toothHeight(code) {
  const [, , ch, rh] = dims(code);
  return ch + rh;
}
