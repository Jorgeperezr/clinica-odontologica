"use client";

/**
 * Odontograma FDI interactivo (SVG).
 * Dibuja los 4 cuadrantes de dentición permanente (11-18, 21-28,
 * 31-38, 41-48). Cada pieza se pinta con el color del estado actual
 * y al hacer clic dispara onToothClick(fdiCode).
 * Es la firma visual del sistema (RF-HCL-02).
 */

const UPPER_RIGHT = ["18", "17", "16", "15", "14", "13", "12", "11"];
const UPPER_LEFT = ["21", "22", "23", "24", "25", "26", "27", "28"];
const LOWER_LEFT = ["31", "32", "33", "34", "35", "36", "37", "38"];
const LOWER_RIGHT = ["48", "47", "46", "45", "44", "43", "42", "41"];

const SIZE = 34;      // tamaño de cada pieza
const GAP = 6;        // separación entre piezas
const MIDGAP = 22;    // separación entre hemiarcadas

function Tooth({ code, x, y, fill, label, onClick, selected }) {
  return (
    <g onClick={() => onClick(code)} style={{ cursor: "pointer" }}
       role="button" aria-label={`Pieza ${code}${label ? `: ${label}` : ""}`}>
      <rect
        x={x} y={y} width={SIZE} height={SIZE} rx={8}
        fill={fill || "#ffffff"}
        stroke={selected ? "var(--petrol)" : "var(--line)"}
        strokeWidth={selected ? 3 : 1.5}
      />
      <text x={x + SIZE / 2} y={y + SIZE / 2 + 4} textAnchor="middle"
            fontSize="12" fontWeight="600"
            fill={isDark(fill) ? "#fff" : "var(--ink)"}>
        {code}
      </text>
    </g>
  );
}

function isDark(hex) {
  if (!hex || hex.length !== 7) return false;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 < 140;
}

export default function Odontogram({ teethState, onToothClick, selectedTooth }) {
  // teethState: { "16": { color, label }, ... } (estado actual por pieza)
  const rowWidth = 8 * (SIZE + GAP) - GAP;
  const totalW = rowWidth * 2 + MIDGAP;
  const totalH = SIZE * 2 + 46;

  const renderRow = (codes, xStart, y) =>
    codes.map((code, i) => {
      const st = teethState[code] || {};
      return (
        <Tooth key={code} code={code}
               x={xStart + i * (SIZE + GAP)} y={y}
               fill={st.color} label={st.label}
               selected={selectedTooth === code}
               onClick={onToothClick} />
      );
    });

  return (
    <svg viewBox={`0 0 ${totalW} ${totalH}`} style={{ width: "100%", maxWidth: 720 }}
         aria-label="Odontograma">
      {/* Arcada superior */}
      {renderRow(UPPER_RIGHT, 0, 0)}
      {renderRow(UPPER_LEFT, rowWidth + MIDGAP, 0)}
      {/* Línea media */}
      <line x1={rowWidth + MIDGAP / 2} y1={-2} x2={rowWidth + MIDGAP / 2} y2={totalH}
            stroke="var(--line)" strokeDasharray="4 4" />
      {/* Arcada inferior */}
      {renderRow(LOWER_RIGHT, 0, SIZE + 42)}
      {renderRow(LOWER_LEFT, rowWidth + MIDGAP, SIZE + 42)}
    </svg>
  );
}
