"use client";

/**
 * Contrato de representación del odontograma (Sprint 46).
 * ────────────────────────────────────────────────────────────────────
 * Patrón Strategy: la lógica de negocio (qué se registra, cómo se guarda,
 * cómo se calculan los índices) vive UNA sola vez en el contenedor
 * `OdontogramTab`; cada modelo visual es una estrategia intercambiable
 * que solo sabe DIBUJAR y EMITIR intenciones.
 *
 * Todo renderizador recibe exactamente estas props y no otras:
 *
 *   surfacesByTooth : { "16": { vestibular: {color, label}, ... }, ... }
 *   rmByTooth       : { "16": { recession: 2, mobility: 1 }, ... }
 *   selectedTooth   : "16" | null
 *   selectedSurface : "whole" | "vestibular" | ... | null
 *   onSurfaceClick(fdiCode, surface)   ← intención de seleccionar
 *   onRMClick(fdiCode, kind)           ← intención de editar recesión/movilidad
 *
 * Consecuencia arquitectónica importante: como ningún modelo guarda
 * estado propio ni escribe en la API, cambiar de vista no puede alterar
 * ni duplicar información. Los tres son ventanas sobre los mismos datos,
 * y el historial, los índices CPO-ceo, los diagnósticos y las
 * exportaciones (PDF y formulario oficial) se generan siempre desde lo
 * almacenado, con independencia del modelo usado para registrar.
 *
 * Para añadir un cuarto modelo basta con crear un componente que respete
 * este contrato y registrarlo en `registry.js`; no hay que tocar la
 * lógica clínica.
 */

// ── Disposición FDI, compartida por todos los modelos ──
export const PERM_UPPER_R = ["18", "17", "16", "15", "14", "13", "12", "11"];
export const PERM_UPPER_L = ["21", "22", "23", "24", "25", "26", "27", "28"];
export const TEMP_UPPER_R = ["55", "54", "53", "52", "51"];
export const TEMP_UPPER_L = ["61", "62", "63", "64", "65"];
export const TEMP_LOWER_R = ["85", "84", "83", "82", "81"];
export const TEMP_LOWER_L = ["71", "72", "73", "74", "75"];
export const PERM_LOWER_R = ["48", "47", "46", "45", "44", "43", "42", "41"];
export const PERM_LOWER_L = ["31", "32", "33", "34", "35", "36", "37", "38"];

export const SURFACES = ["vestibular", "distal", "palatal_lingual", "mesial", "occlusal"];

export const SURFACE_LABELS = {
  whole: "Toda la pieza",
  vestibular: "Vestibular",
  palatal_lingual: "Palatina / Lingual",
  mesial: "Mesial",
  distal: "Distal",
  occlusal: "Oclusal / Incisal",
};

/** Estado dominante de una pieza: el primero con color registrado. */
export function dominantState(surfaces) {
  if (!surfaces) return null;
  for (const s of ["occlusal", ...SURFACES]) {
    if (surfaces[s]?.color) return surfaces[s];
  }
  return null;
}

/** ¿La pieza tiene algún registro? */
export function hasRecords(surfaces) {
  return Boolean(surfaces && Object.values(surfaces).some((v) => v?.color));
}
