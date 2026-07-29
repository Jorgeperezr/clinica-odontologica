"use client";

/**
 * Modelo ANATÓMICO (Sprint 46).
 *
 * Representa cada pieza con la silueta de su corona —incisivo, canino,
 * premolar o molar según el número FDI— acompañada de una rueda de cinco
 * superficies. Es el modelo que replica el aspecto de los odontogramas
 * de escritorio clásicos: la forma ayuda a ubicarse rápido en la boca,
 * y la rueda mantiene la precisión por superficie.
 *
 * Cumple el contrato de `contract.js`: solo dibuja y emite intenciones.
 * No guarda estado ni escribe en la API.
 */

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACES, TEMP_LOWER_L, TEMP_LOWER_R, TEMP_UPPER_L, TEMP_UPPER_R,
  dominantState,
} from "./contract";

const W = 46;        // ancho de celda
const CROWN_H = 40;  // alto de la corona
const WHEEL = 32;    // diámetro de la rueda de superficies
const GAP = 4;

/** Familia de la pieza según el último dígito FDI. */
function toothKind(code) {
  const n = Number(String(code).slice(-1));
  if (n <= 2) return "incisivo";
  if (n === 3) return "canino";
  if (n <= 5) return "premolar";
  return "molar";
}

/** Silueta de la corona. `up` invierte para la arcada inferior. */
function crownPath(kind, up) {
  const w = 26, h = CROWN_H - 6;
  const shapes = {
    // borde incisal recto y raíz estrecha
    incisivo: `M2 ${h} L2 8 Q2 2 ${w / 2} 2 Q${w - 2} 2 ${w - 2} 8 L${w - 2} ${h} Z`,
    // cúspide central marcada
    canino: `M2 ${h} L2 10 Q${w / 2} -3 ${w - 2} 10 L${w - 2} ${h} Z`,
    // dos cúspides
    premolar: `M2 ${h} L2 12 Q${w * 0.28} 2 ${w / 2} 9 Q${w * 0.72} 2 ${w - 2} 12 L${w - 2} ${h} Z`,
    // cuatro cúspides
    molar: `M2 ${h} L2 13 Q${w * 0.2} 4 ${w * 0.35} 10 Q${w / 2} 3 ${w * 0.65} 10 Q${w * 0.8} 4 ${w - 2} 13 L${w - 2} ${h} Z`,
  };
  return { d: shapes[kind], w, h, flip: !up };
}

function Crown({ code, x, y, up, state, selected, onClick }) {
  const kind = toothKind(code);
  const { d, w, h, flip } = crownPath(kind, up);
  const ox = x + (W - w) / 2;
  return (
    <g transform={flip ? `translate(${ox}, ${y + h}) scale(1,-1)` : `translate(${ox}, ${y})`}
       onClick={() => onClick(code, "whole")} style={{ cursor: "pointer" }}>
      <title>{`Pieza ${code} — seleccionar toda la pieza`}</title>
      <path d={d} fill={state?.color || "var(--card)"}
            stroke={selected ? "var(--petrol)" : "var(--line-strong)"}
            strokeWidth={selected ? 2.2 : 1.1} />
    </g>
  );
}

/** Rueda de cinco superficies: cuatro cuadrantes + centro oclusal. */
function SurfaceWheel({ code, x, y, surfaces, selectedSurface, selected, onClick }) {
  const r = WHEEL / 2, cx = x + W / 2, cy = y + r;
  const inner = r * 0.42;
  // cuadrantes: vestibular arriba, palatino abajo, mesial/distal a los lados
  const quad = (a0, a1) => {
    const p = (a, rad) => [cx + rad * Math.cos(a), cy + rad * Math.sin(a)];
    const [x0, y0] = p(a0, r), [x1, y1] = p(a1, r);
    const [x2, y2] = p(a1, inner), [x3, y3] = p(a0, inner);
    return `M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1} L${x2} ${y2} A${inner} ${inner} 0 0 0 ${x3} ${y3} Z`;
  };
  const D = Math.PI / 4;
  const geom = {
    vestibular: quad(-3 * D, -D),
    mesial: quad(-D, D),
    palatal_lingual: quad(D, 3 * D),
    distal: quad(3 * D, 5 * D),
  };

  return (
    <g aria-label={`Superficies de la pieza ${code}`}>
      {SURFACES.filter((s) => s !== "occlusal").map((s) => (
        <path key={s} d={geom[s]}
              fill={surfaces?.[s]?.color || "var(--card)"}
              stroke={(selected && selectedSurface === s) ? "var(--petrol)" : "var(--line-strong)"}
              strokeWidth={(selected && selectedSurface === s) ? 2 : 0.9}
              onClick={() => onClick(code, s)} style={{ cursor: "pointer" }}>
          <title>{`Pieza ${code} — ${s}`}</title>
        </path>
      ))}
      <circle cx={cx} cy={cy} r={inner}
              fill={surfaces?.occlusal?.color || "var(--card)"}
              stroke={(selected && selectedSurface === "occlusal") ? "var(--petrol)" : "var(--line-strong)"}
              strokeWidth={(selected && selectedSurface === "occlusal") ? 2 : 0.9}
              onClick={() => onClick(code, "occlusal")} style={{ cursor: "pointer" }}>
        <title>{`Pieza ${code} — oclusal`}</title>
      </circle>
    </g>
  );
}

export default function AnatomicalView({
  surfacesByTooth = {}, selectedTooth, selectedSurface, onSurfaceClick,
}) {
  const rowW = (codes) => codes.length * (W + GAP) - GAP;
  const halfW = rowW(PERM_UPPER_R);
  const MID = 22;
  const totalW = halfW * 2 + MID;

  const xR = (i, n) => halfW - n * (W + GAP) + GAP + i * (W + GAP);
  const xL = (i) => halfW + MID + i * (W + GAP);

  // Alturas de fila: corona + rueda + número
  const ROW = CROWN_H + WHEEL + 22;
  const rows = [
    { key: "pu", up: true, y: 0, R: PERM_UPPER_R, L: PERM_UPPER_L },
    { key: "tu", up: true, y: ROW + 8, R: TEMP_UPPER_R, L: TEMP_UPPER_L },
    { key: "tl", up: false, y: (ROW + 8) * 2, R: TEMP_LOWER_R, L: TEMP_LOWER_L },
    { key: "pl", up: false, y: (ROW + 8) * 3, R: PERM_LOWER_R, L: PERM_LOWER_L },
  ];
  const totalH = (ROW + 8) * 4;

  function renderTooth(code, x, y, up) {
    const surfaces = surfacesByTooth[code];
    const selected = selectedTooth === code;
    // Arriba: corona sobre rueda. Abajo: rueda sobre corona (espejo anatómico)
    const crownY = up ? y : y + WHEEL + 18;
    const wheelY = up ? y + CROWN_H + 4 : y;
    const labelY = up ? y + CROWN_H + WHEEL + 18 : y + WHEEL + 14;
    return (
      <g key={code}>
        <Crown code={code} x={x} y={crownY} up={up}
               state={dominantState(surfaces)} selected={selected}
               onClick={onSurfaceClick} />
        <SurfaceWheel code={code} x={x} y={wheelY} surfaces={surfaces}
                      selectedSurface={selectedSurface} selected={selected}
                      onClick={onSurfaceClick} />
        <text x={x + W / 2} y={labelY} textAnchor="middle" fontSize="11.5"
              fontWeight="700" fill={selected ? "var(--petrol)" : "var(--ink)"}
              onClick={() => onSurfaceClick(code, "whole")} style={{ cursor: "pointer" }}>
          {code}
        </text>
      </g>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${totalW} ${totalH}`} width="100%"
           style={{ minWidth: 760, display: "block" }}
           role="img" aria-label="Odontograma anatómico">
        {/* Línea media */}
        <line x1={halfW + MID / 2} y1={0} x2={halfW + MID / 2} y2={totalH}
              stroke="var(--line)" strokeDasharray="4 4" strokeWidth="1" />
        {rows.map((r) => (
          <g key={r.key}>
            {r.R.map((code, i) => renderTooth(code, xR(i, r.R.length), r.y, r.up))}
            {r.L.map((code, i) => renderTooth(code, xL(i), r.y, r.up))}
          </g>
        ))}
      </svg>
    </div>
  );
}
