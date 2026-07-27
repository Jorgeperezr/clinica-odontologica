"use client";

/**
 * Selector de apariencia: Claro · Oscuro · Sistema.
 *
 * Tres estados explícitos en vez de un interruptor de dos: "Sistema"
 * es una preferencia real y distinta —seguir al sistema operativo— y
 * esconderla detrás de un toggle obliga a la persona a re-elegir cada
 * vez que su equipo cambia de modo.
 *
 * El indicador se desliza entre opciones; en el modo de movimiento
 * reducido simplemente aparece (lo resuelve globals.css).
 */

import { useEffect, useState } from "react";

import { onColorModeChanged, readColorMode, setColorMode } from "./theme";

const OPTIONS = [
  { key: "light", label: "Claro", icon: SunIcon },
  { key: "dark", label: "Oscuro", icon: MoonIcon },
  { key: "system", label: "Sistema", icon: SystemIcon },
];

const svg = {
  width: 15, height: 15, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.9,
  strokeLinecap: "round", strokeLinejoin: "round",
};

function SunIcon() {
  return (
    <svg {...svg}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" />
    </svg>
  );
}
function MoonIcon() {
  return (
    <svg {...svg}>
      <path d="M20 14.5A8.2 8.2 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5Z" />
    </svg>
  );
}
function SystemIcon() {
  return (
    <svg {...svg}>
      <rect x="2.8" y="4.5" width="18.4" height="12" rx="1.6" />
      <path d="M8.5 20h7M12 16.5V20" />
    </svg>
  );
}

export default function ThemeSwitch({ compact = false }) {
  const [mode, setMode] = useState("system");

  useEffect(() => {
    setMode(readColorMode());
    return onColorModeChanged((d) => setMode(d.mode));
  }, []);

  const index = Math.max(0, OPTIONS.findIndex((o) => o.key === mode));

  return (
    <div role="radiogroup" aria-label="Apariencia"
         style={{
           position: "relative", display: "grid",
           gridTemplateColumns: `repeat(${OPTIONS.length}, 1fr)`,
           gap: 2, padding: 3, borderRadius: 999,
           background: "rgba(255,255,255,.10)",
           border: "1px solid rgba(255,255,255,.14)",
         }}>
      {/* Indicador deslizante */}
      <span aria-hidden="true"
            style={{
              position: "absolute", top: 3, bottom: 3,
              left: `calc(${(index * 100) / OPTIONS.length}% + 3px)`,
              width: `calc(${100 / OPTIONS.length}% - 6px)`,
              borderRadius: 999,
              background: "rgba(255,255,255,.92)",
              transition: "left var(--dur) var(--ease)",
            }} />
      {OPTIONS.map((o) => {
        const active = o.key === mode;
        const Icon = o.icon;
        return (
          <button key={o.key} type="button" role="radio" aria-checked={active}
                  title={o.label} aria-label={o.label}
                  onClick={() => setColorMode(o.key)}
                  style={{
                    position: "relative", zIndex: 1,
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    gap: 6, padding: compact ? "5px 0" : "5px 8px",
                    background: "transparent", border: "none", borderRadius: 999,
                    color: active ? "var(--petrol-deep)" : "rgba(255,255,255,.82)",
                    fontSize: 12, fontWeight: 600, cursor: "pointer",
                    transition: "color var(--dur) var(--ease)",
                  }}>
            <Icon />
            {!compact && <span>{o.label}</span>}
          </button>
        );
      })}
    </div>
  );
}
