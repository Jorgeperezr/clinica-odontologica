"use client";

/**
 * Registro de modelos de odontograma (Sprint 46).
 *
 * Punto único de extensión: para añadir un modelo nuevo se crea un
 * componente que respete el contrato de `contract.js` y se agrega aquí.
 * Ni la lógica clínica ni el contenedor necesitan cambios.
 *
 * El orden importa: el primero es el modelo predeterminado.
 */

import ClassicOdontogram from "../Odontogram";
import AnatomicalView from "./AnatomicalView";
import CompactView from "./CompactView";

export const VIEWS = [
  {
    key: "clasico",
    label: "Clásico",
    description: "Esquema MSP por superficies. Vista predeterminada.",
    Component: ClassicOdontogram,
  },
  {
    key: "anatomico",
    label: "Anatómico",
    description: "Siluetas dentales con rueda de superficies.",
    Component: AnatomicalView,
  },
  {
    key: "compacto",
    label: "Compacto",
    description: "Cuadrícula por cuadrantes, ideal para pantallas pequeñas.",
    Component: CompactView,
  },
];

export const DEFAULT_VIEW = VIEWS[0].key;

const STORAGE_KEY = "odontogramView";

/** Modelo preferido de esta persona (no viaja al servidor: es una preferencia de vista). */
export function readPreferredView() {
  if (typeof localStorage === "undefined") return DEFAULT_VIEW;
  const v = localStorage.getItem(STORAGE_KEY);
  return VIEWS.some((x) => x.key === v) ? v : DEFAULT_VIEW;
}

export function savePreferredView(key) {
  try { localStorage.setItem(STORAGE_KEY, key); } catch { /* modo privado */ }
}

export function getView(key) {
  return VIEWS.find((v) => v.key === key) || VIEWS[0];
}
