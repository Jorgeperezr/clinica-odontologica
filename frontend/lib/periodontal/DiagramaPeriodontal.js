"use client";

/**
 * Diagrama del periodontograma: las piezas con sus raíces y, encima, el
 * margen gingival y el fondo de la bolsa.
 * ────────────────────────────────────────────────────────────────────
 * Es la lectura que da sentido a los números de sondaje: una bolsa de
 * 6 mm se VE como una zona sombreada que baja por la raíz, y una
 * recesión como el margen rojo alejándose del cuello.
 *
 *   · línea roja  → margen gingival
 *   · línea azul  → fondo de la bolsa (margen + profundidad de sondaje)
 *   · sombreado   → la bolsa, entre las dos
 *
 * Todo en milímetros reales desde la unión amelocementaria de CADA pieza
 * (`marcoVestibular`): el cuello de un canino no está a la misma altura
 * que el de un molar, y medir desde una línea común falsearía la
 * profundidad. Convención del modelo: el margen gingival positivo es
 * recesión (apical al cuello) y el nivel de inserción es
 * profundidad + margen.
 *
 * Solo dibuja. No guarda nada ni conoce la API.
 */

import { dominantState } from "../odontogram/contract";
import { VistaVestibular, marcoVestibular } from "../odontogram/AnatomiaDental";
import { CELL_W } from "./cells";

/** Píxeles por milímetro: el molar más ancho cabe en su columna. */
export const ESCALA = 4.2;
const COL = CELL_W + 8;
const PROFUNDIDAD_ALERTA = 4;      // > 4 mm: bolsa patológica

const COLOR_MARGEN = "#d64545";
const COLOR_FONDO = "#2f6fd6";

/**
 * Una cara (vestibular o palatina/lingual) de un cuadrante.
 *
 * @param codes  piezas del cuadrante, en el orden de la pantalla
 * @param cara   "v" (sitios 0–2) o "l" (sitios 3–5)
 * @param byCode mediciones por pieza, o {} si no hay ficha
 */
export function DiagramaCara({ codes, cara, byCode = {}, surfacesByTooth = {},
                               selectedTooth, onSurfaceClick, etiqueta }) {
  const base = cara === "v" ? 0 : 3;
  const alto = marcoVestibular(codes[0]).alto * ESCALA;
  const ancho = codes.length * COL;

  /* Puntos de cada pieza, de izquierda a derecha en pantalla. Una pieza
     ausente corta las líneas: unirlas por encima del hueco inventaría
     un margen que no existe. */
  const tramos = [];
  let actual = [];
  codes.forEach((code, i) => {
    const t = byCode[code];
    if (!t || !t.is_present) {
      if (actual.length) tramos.push(actual);
      actual = [];
      return;
    }
    const m = marcoVestibular(code);
    const izq = i * COL + (COL - m.ancho * ESCALA) / 2;
    const pts = [0, 1, 2].map((k) => {
      const gm = t.gingival_margin?.[base + k] ?? 0;
      const pd = t.probing_depth?.[base + k] ?? 0;
      return {
        x: izq + m.sitios[k] * ESCALA,
        margen: (m.cuello + m.apical * gm) * ESCALA,
        fondo: (m.cuello + m.apical * (gm + pd)) * ESCALA,
        pd,
        sangra: Boolean(t.bleeding?.[base + k]),
      };
    }).sort((a, b) => a.x - b.x);
    actual.push(...pts);
  });
  if (actual.length) tramos.push(actual);

  const linea = (pts, campo) => pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p[campo].toFixed(1)}`).join(" ");

  return (
    <div role="img" aria-label={etiqueta}
         style={{ position: "relative", display: "flex", width: ancho, height: alto, flexShrink: 0 }}>
      {/* Pauta de milímetros: referencia visual, como el papel de la ficha. */}
      <svg aria-hidden="true" width={ancho} height={alto}
           style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {Array.from({ length: Math.floor(alto / (ESCALA * 2)) }, (_, k) => (
          <line key={k} x1="0" x2={ancho} y1={(k + 1) * ESCALA * 2} y2={(k + 1) * ESCALA * 2}
                stroke="var(--line)" strokeWidth="0.6" opacity="0.55" />
        ))}
      </svg>

      {codes.map((code) => {
        const t = byCode[code];
        const sel = selectedTooth === code;
        return (
          <div key={code} style={{ width: COL, flexShrink: 0, display: "flex", justifyContent: "center",
                                   background: sel ? "var(--petrol-soft)" : "transparent",
                                   position: "relative" }}>
            <VistaVestibular code={code} escala={ESCALA} seleccionado={sel}
                             estado={dominantState(surfacesByTooth[code])}
                             implante={Boolean(t?.has_implant)}
                             ausente={t ? !t.is_present : false}
                             onClick={() => onSurfaceClick?.(code, "whole")} />
          </div>
        );
      })}

      <svg aria-hidden="true" width={ancho} height={alto}
           style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "visible" }}>
        {tramos.map((pts, i) => (
          <g key={i}>
            <path d={`${linea(pts, "margen")} ${pts.slice().reverse().map((p) => `L${p.x.toFixed(1)} ${p.fondo.toFixed(1)}`).join(" ")} Z`}
                  fill={COLOR_FONDO} opacity="0.18" />
            <path d={linea(pts, "margen")} fill="none" stroke={COLOR_MARGEN} strokeWidth="1.7"
                  strokeLinejoin="round" />
            <path d={linea(pts, "fondo")} fill="none" stroke={COLOR_FONDO} strokeWidth="1.7"
                  strokeLinejoin="round" />
            {pts.map((p, k) => (
              <g key={k}>
                <circle cx={p.x} cy={p.margen} r="2" fill={COLOR_MARGEN} />
                {/* El punto del fondo se agranda y se pinta de rojo si
                    sangra: la bolsa que sangra es la que está activa. */}
                <circle cx={p.x} cy={p.fondo} r={p.sangra ? 2.8 : 2}
                        fill={p.sangra ? COLOR_MARGEN : COLOR_FONDO}
                        stroke={p.pd > PROFUNDIDAD_ALERTA ? "var(--card)" : "none"} strokeWidth="1" />
              </g>
            ))}
          </g>
        ))}
      </svg>
    </div>
  );
}

/** Leyenda del diagrama. */
export function LeyendaPeriodontal() {
  const item = (color, texto, forma = "linea") => (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      {forma === "linea"
        ? <span style={{ width: 18, height: 2.5, background: color, borderRadius: 2 }} />
        : forma === "punto"
          ? <span style={{ width: 8, height: 8, background: color, borderRadius: "50%" }} />
          : <span style={{ width: 14, height: 10, background: color, opacity: 0.25, borderRadius: 2 }} />}
      {texto}
    </span>
  );
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "var(--ink-soft)" }}>
      {item(COLOR_MARGEN, "Margen gingival")}
      {item(COLOR_FONDO, "Fondo de bolsa")}
      {item(COLOR_FONDO, "Bolsa", "zona")}
      {item(COLOR_MARGEN, "Sangrado al sondaje", "punto")}
    </div>
  );
}
