"use client";

import { apiBase } from "./api";

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
// «default» es la paleta original de Clinube: cian sobre tinta. `nav` es
// el fondo de la barra lateral en modo claro; sin él, la barra toma el
// tono hondo del color principal. «sin_color» es el logotipo en grises
// —el de imprimir en blanco y negro, sellar o mandar por fax— llevado a
// todo el panel: cambia los colores y nada más.
// La misma tabla vive en apps/configuration/temas.py (hay una prueba).
export const PRESETS = [
  { key: "default", label: "Clinube (original)", primary: "#0e7490", secondary: "#67e8f9", nav: "#0b1220" },
  { key: "sin_color", label: "Sin color", primary: "#404040", secondary: "#9ca3af", nav: "#111111" },
  { key: "oceano", label: "Océano", primary: "#0f4c81", secondary: "#a7d3f0" },
  { key: "petroleo", label: "Petróleo", primary: "#0e5c63", secondary: "#9fe1cb" },
  { key: "bosque", label: "Bosque", primary: "#1d6b3c", secondary: "#b6e2c5" },
  { key: "vino", label: "Vino", primary: "#7b1e3c", secondary: "#f0c9d4" },
  { key: "grafito", label: "Grafito", primary: "#374151", secondary: "#c7d2de" },
  { key: "arena", label: "Arena", primary: "#8a5a2b", secondary: "#ecd9bd" },
];

const DEFAULT = PRESETS[0];
const SIN_COLOR = PRESETS.find((p) => p.key === "sin_color");

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

/** Contraste de un color contra un fondo cualquiera. */
function contrastRatio(hexA, hexB) {
  const la = luminance(hexA), lb = luminance(hexB);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Aclara el color hasta que contraste AA (4.5:1) con el fondo oscuro.
 * En modo oscuro la marca se usa sobre superficies profundas: el mismo
 * tono que funciona en claro quedaría ilegible, así que se sube su
 * luminosidad conservando matiz y saturación (la identidad se mantiene).
 */
export function ensureAccessibleOnDark(hex, bg = "#0f1618") {
  if (!hexToRgb(hex)) return null;
  const [h, s0, l0] = rgbToHsl(hexToRgb(hex));
  // Sobre fondo oscuro un tono saturado "grita": al aclararlo se vuelve
  // fluorescente. Se atenúa la saturación para obtener un acento suave
  // que conserva el matiz —y por tanto la identidad— sin estridencia.
  const s = Math.min(s0 * 0.78, 0.52);
  let l = l0;
  let out = rgbToHex(hslToRgb([h, s, l]));
  let guard = 0;
  while (contrastRatio(out, bg) < 4.5 && l < 0.95 && guard < 50) {
    l += 0.02;
    out = rgbToHex(hslToRgb([h, s, l]));
    guard += 1;
  }
  return out;
}

// Último tema aplicado: al cambiar de modo se recalcula sobre él.
let lastTheme = null;

/**
 * Aplica el tema recalculando las variables CSS de marca.
 * El modo (claro/oscuro) determina cómo se derivan los tonos:
 * en claro se oscurece la marca para contrastar con texto blanco;
 * en oscuro se aclara para contrastar con el fondo profundo.
 */
export function applyTheme(theme, mode) {
  if (typeof document === "undefined") return;
  if (theme) lastTheme = theme;
  const effective = theme || lastTheme;
  // «Sin color» elegido por la persona manda sobre el tema de la clínica,
  // pero solo en su pantalla: no toca lo que ven los demás.
  const tema = readSinColor() ? { ...SIN_COLOR } : resolveTheme(effective);
  const { primary, secondary } = tema;
  const root = document.documentElement;
  const isDark = (mode || root.getAttribute("data-theme")) === "dark";
  // globals.css cuelga de aquí las superficies en grises de «Sin color».
  root.setAttribute("data-paleta", tema.key || "custom");
  // La barra lateral propia del tema, solo en claro: en oscuro la
  // navegación es siempre una superficie neutra (ver globals.css).
  if (tema.nav && !isDark) root.style.setProperty("--nav-bg", tema.nav);
  else root.style.removeProperty("--nav-bg");

  const base = hexToRgb(primary) ? primary : DEFAULT.primary;
  const brand = isDark
    ? (ensureAccessibleOnDark(base) || DEFAULT.primary)
    : (ensureAccessiblePrimary(base) || DEFAULT.primary);
  const brandL = rgbToHsl(hexToRgb(brand))[2];

  root.style.setProperty("--petrol", brand);
  // "deep" = estado hover: en claro se hunde, en oscuro se aclara más
  root.style.setProperty(
    "--petrol-deep",
    isDark ? withLightness(brand, Math.min(0.86, brandL + 0.10))
           : withLightness(brand, Math.max(0.10, brandL - 0.12)),
  );
  // "soft" = fondo de realce: casi blanco en claro, tinte profundo en oscuro
  if (isDark) {
    // Realce: tinte muy profundo y desaturado, para franjas de hover
    const [bh, bs] = rgbToHsl(hexToRgb(brand));
    root.style.setProperty("--petrol-soft",
      rgbToHex(hslToRgb([bh, Math.min(bs, 0.28), 0.155])));
  } else {
    root.style.setProperty("--petrol-soft", withLightness(brand, 0.93));
  }

  const mint = hexToRgb(secondary) ? secondary : DEFAULT.secondary;
  const mintL = rgbToHsl(hexToRgb(mint))[2];
  root.style.setProperty(
    "--mint",
    isDark ? withLightness(mint, 0.62) : withLightness(mint, Math.max(0.72, mintL)),
  );
}

/* ═══════════ Modo de color: claro / oscuro / sistema ═══════════ */

const MODE_KEY = "colorMode";           // "light" | "dark" | "system"
const MODE_EVENT = "colormode:changed";

export function readColorMode() {
  if (typeof localStorage === "undefined") return "system";
  return localStorage.getItem(MODE_KEY) || "system";
}

function systemPrefersDark() {
  return typeof window !== "undefined"
    && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

/** Modo efectivo ("light" | "dark") resolviendo "system". */
export function resolvedMode(mode = readColorMode()) {
  return mode === "system" ? (systemPrefersDark() ? "dark" : "light") : mode;
}

/** Fija el modo, lo persiste y recalcula la marca para ese modo. */
export function setColorMode(mode) {
  if (typeof document === "undefined") return;
  try { localStorage.setItem(MODE_KEY, mode); } catch { /* modo privado */ }
  const effective = resolvedMode(mode);
  document.documentElement.setAttribute("data-theme", effective);
  applyTheme(null, effective);
  window.dispatchEvent(new CustomEvent(MODE_EVENT, { detail: { mode, effective } }));
}

/**
 * Arranca el modo guardado y sigue los cambios del sistema operativo
 * mientras la preferencia sea "system". Devuelve la función de limpieza.
 */
export function initColorMode() {
  if (typeof window === "undefined") return () => {};
  setColorMode(readColorMode());
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onChange = () => { if (readColorMode() === "system") setColorMode("system"); };
  mq.addEventListener?.("change", onChange);
  return () => mq.removeEventListener?.("change", onChange);
}

export function onColorModeChanged(handler) {
  if (typeof window === "undefined") return () => {};
  const fn = (e) => handler(e.detail);
  window.addEventListener(MODE_EVENT, fn);
  return () => window.removeEventListener(MODE_EVENT, fn);
}

/* ═══════════ «Sin color», preferencia de cada persona ═══════════ */

const SIN_COLOR_KEY = "sinColor";
const SIN_COLOR_EVENT = "sincolor:changed";

export function readSinColor() {
  try { return localStorage.getItem(SIN_COLOR_KEY) === "1"; } catch { return false; }
}

/** Activa o quita «Sin color» en este navegador y repinta al momento. */
export function setSinColor(activo) {
  try {
    if (activo) localStorage.setItem(SIN_COLOR_KEY, "1");
    else localStorage.removeItem(SIN_COLOR_KEY);
  } catch { /* modo privado: vale para esta visita */ }
  applyTheme(null);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(SIN_COLOR_EVENT, { detail: { activo } }));
  }
}

export function onSinColorChanged(handler) {
  if (typeof window === "undefined") return () => {};
  const fn = (e) => handler(e.detail.activo);
  window.addEventListener(SIN_COLOR_EVENT, fn);
  return () => window.removeEventListener(SIN_COLOR_EVENT, fn);
}

/** Restablece las variables al tema del sistema. */
export function resetTheme() {
  applyTheme({ preset: "default" });
}

// ── identidad de la clínica: caché + notificación en vivo (Sprint 34) ──
const BRANDING_KEY = "clinicBranding";
const BRANDING_EVENT = "branding:updated";

export function readBrandingCache() {
  try { return JSON.parse(localStorage.getItem(BRANDING_KEY) || "null"); } catch { return null; }
}

export function saveBrandingCache(branding) {
  try { localStorage.setItem(BRANDING_KEY, JSON.stringify(branding)); } catch {}
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(BRANDING_EVENT, { detail: branding }));
  }
}

export function onBrandingUpdated(handler) {
  if (typeof window === "undefined") return () => {};
  const fn = (e) => handler(e.detail);
  window.addEventListener(BRANDING_EVENT, fn);
  return () => window.removeEventListener(BRANDING_EVENT, fn);
}

/** Aplica favicon y título del documento según la identidad de la clínica. */
export function applyBrandingChrome(branding) {
  if (typeof document === "undefined" || !branding) return;
  const name = branding.display_name || branding.nombre_clinica || "Clinube";
  document.title = name;
  if (branding.logo_url) {
    let link = document.querySelector("link[rel='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.href = logoSrc(branding.logo_url, branding.updated_at);
  }
}


/**
 * Resuelve una ruta relativa del backend contra el host de la API, en
 * https, evitando el bloqueo por contenido mixto. Si ya es absoluta —el
 * caso del bucket— se respeta tal cual.
 *
 * Sirve para archivos PÚBLICOS. Los documentos clínicos ya no se
 * resuelven así: los entrega un endpoint autenticado y se cargan con
 * `AuthImage` o con `DocumentPreview` (Sprint 66).
 */
export function fileSrc(url) {
  if (!url) return null;
  if (/^https?:\/\//i.test(url)) return url;
  return `${apiBase()}${url.startsWith("/") ? "" : "/"}${url}`;
}

export function logoSrc(url, version) {
  if (!url) return null;
  const abs = /^https?:\/\//i.test(url)
    ? url
    : `${apiBase()}${url.startsWith("/") ? "" : "/"}${url}`;
  // Al reemplazar el logotipo la ruta puede repetirse; sin versionar, el
  // navegador seguiría mostrando la imagen cacheada.
  if (!version) return abs;
  return `${abs}${abs.includes("?") ? "&" : "?"}v=${encodeURIComponent(version)}`;
}
