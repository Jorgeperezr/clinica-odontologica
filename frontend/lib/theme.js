"use client";

/**
 * Motor de temas por clínica (Sprint 33).
 *
 * El sistema entero pinta con variables CSS (--petrol, --petrol-deep,
 * --petrol-soft, --mint...). Personalizar la identidad visual es, por
 * tanto, recalcular esas variables a partir de un color primario y uno
 * secundario, y aplicarlas en :root. Barra lateral, botones, enlaces,
 * pestañas activas, indicadores y tarjetas se re-tiñen solos.
 *
 * Accesibilidad: el primario se oscurece automáticamente hasta que el
 * texto blanco contraste al menos 4.5:1 (WCAG AA); el tono "soft" se
 * genera muy claro para servir de fondo con texto oscuro.
 */

// ── utilidades de color ──
function hexToRgb(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || "");
  return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : null;
}
function rgbToHex([r, g, b]) {
  return "#" + [r, g, b].map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
}
function rgbToHsl([r, g, b]) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
  }
  return [h, s, l];
}
function hslToRgb([h, s, l]) {
  if (s === 0) { const v = l * 255; return [v, v, v]; }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const f = (t) => {
    if (t < 0) t += 1; if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [f(h + 1 / 3) * 255, f(h) * 255, f(h - 1 / 3) * 255];
}
function withLightness(hex, l) {
  const hsl = rgbToHsl(hexToRgb(hex));
  return rgbToHex(hslToRgb([hsl[0], hsl[1], l]));
}
function luminance(hex) {
  const [r, g, b] = hexToRgb(hex).map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrastWithWhite(hex) {
  return 1.05 / (luminance(hex) + 0.05);
}

/** Oscurece el color hasta que el texto blanco alcance contraste AA (4.5:1). */
export function ensureAccessiblePrimary(hex) {
  if (!hexToRgb(hex)) return null;
  let [h, s, l] = rgbToHsl(hexToRgb(hex));
  let out = rgbToHex(hslToRgb([h, s, l]));
  let guard = 0;
  while (contrastWithWhite(out) < 4.5 && l > 0.05 && guard < 40) {
    l -= 0.02;
    out = rgbToHex(hslToRgb([h, s, l]));
    guard += 1;
  }
  return out;
}

// ── temas predefinidos ──
export const PRESETS = [
  { key: "default", label: "Petróleo (sistema)", primary: "#0e5c63", secondary: "#9fe1cb" },
  { key: "oceano", label: "Océano", primary: "#0f4c81", secondary: "#a7d3f0" },
  { key: "bosque", label: "Bosque", primary: "#1d6b3c", secondary: "#b6e2c5" },
  { key: "vino", label: "Vino", primary: "#7b1e3c", secondary: "#f0c9d4" },
  { key: "grafito", label: "Grafito", primary: "#374151", secondary: "#c7d2de" },
  { key: "arena", label: "Arena", primary: "#8a5a2b", secondary: "#ecd9bd" },
];

const DEFAULT = PRESETS[0];

/**
 * Resuelve el tema guardado a los dos colores base.
 * theme = { preset, primary, secondary }
 */
export function resolveTheme(theme) {
  if (!theme || !theme.preset || theme.preset === "default") return { ...DEFAULT };
  const preset = PRESETS.find((p) => p.key === theme.preset);
  if (preset) return { ...preset };
  // "auto" (del logotipo) o "custom": usa los colores guardados
  return {
    key: theme.preset,
    primary: theme.primary || DEFAULT.primary,
    secondary: theme.secondary || DEFAULT.secondary,
  };
}

/** Aplica el tema recalculando las variables CSS globales. */
export function applyTheme(theme) {
  if (typeof document === "undefined") return;
  const { primary, secondary } = resolveTheme(theme);
  const safePrimary = ensureAccessiblePrimary(primary) || DEFAULT.primary;
  const root = document.documentElement;

  root.style.setProperty("--petrol", safePrimary);
  root.style.setProperty("--petrol-deep", withLightness(safePrimary, Math.max(0.10, rgbToHsl(hexToRgb(safePrimary))[2] - 0.12)));
  root.style.setProperty("--petrol-soft", withLightness(safePrimary, 0.93));
  const mint = hexToRgb(secondary) ? secondary : DEFAULT.secondary;
  root.style.setProperty("--mint", withLightness(mint, Math.max(0.72, rgbToHsl(hexToRgb(mint))[2])));
}

/** Restablece las variables al tema del sistema. */
export function resetTheme() {
  applyTheme({ preset: "default" });
}
