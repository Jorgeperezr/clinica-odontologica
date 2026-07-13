"use client";

/**
 * Odontograma oficial MSP HCU-form.033/2021 (SVG interactivo).
 *
 * Distribución exacta del formulario:
 *   - Permanente superior:  18–11 | 21–28
 *   - Temporal superior:    55–51 | 61–65
 *   - Temporal inferior:    85–81 | 71–75
 *   - Permanente inferior:  48–41 | 31–38
 *
 * Cada pieza permanente se dibuja como un cuadrado con un rombo interior
 * (5 superficies clicables: vestibular, lingual/palatina, mesial, distal y
 * oclusal central). Las piezas temporales se dibujan como círculo con las
 * mismas 5 superficies. Cada superficie se pinta con el color del estado
 * vigente de esa cara. Recesión y movilidad se registran por pieza sobre
 * y bajo cada arcada, como en el formulario.
 *
 * La lógica de negocio (registro, historial, índices) no cambia: este
 * componente solo dibuja y emite onSurfaceClick(fdiCode, surface).
 */

const PERM_UPPER_R = ["18", "17", "16", "15", "14", "13", "12", "11"];
const PERM_UPPER_L = ["21", "22", "23", "24", "25", "26", "27", "28"];
const TEMP_UPPER_R = ["55", "54", "53", "52", "51"];
const TEMP_UPPER_L = ["61", "62", "63", "64", "65"];
const TEMP_LOWER_R = ["85", "84", "83", "82", "81"];
const TEMP_LOWER_L = ["71", "72", "73", "74", "75"];
const PERM_LOWER_R = ["48", "47", "46", "45", "44", "43", "42", "41"];
const PERM_LOWER_L = ["31", "32", "33", "34", "35", "36", "37", "38"];

const CELL = 40;       // ancho de celda (pieza)
const GAP = 4;         // separación entre piezas
const MIDGAP = 26;     // separación entre hemiarcadas
const RM_H = 15;       // alto de cada fila recesión/movilidad
const LABEL_H = 14;    // alto de la etiqueta numérica
const ARCADE_GAP = 30; // separación vertical entre arcadas

// Las 5 superficies y su geometría dentro de la celda (0..CELL)
// El rombo interior divide el cuadrado en 4 triángulos + centro.
const M = 0;                 // margen exterior
const C = CELL;              // lado
const IN = CELL * 0.30;      // inset del cuadrado central (oclusal)

function isDark(hex) {
  if (!hex || hex.length !== 7) return false;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return (r * 299 + g * 587 + b * 114) / 1000 < 140;
}

// Polígonos de cada superficie (coordenadas locales dentro de la celda)
function surfacePaths(round) {
  if (round) {
    // Para temporales usamos el mismo esquema de rombo pero recortado
    // visualmente con un círculo (clipPath). Geometría idéntica.
  }
  const a = IN, b = C - IN;
  return {
    // triángulo superior = vestibular (por convención del formulario, arriba)
    vestibular: `${M},${M} ${C},${M} ${b},${a} ${a},${a}`,
    // triángulo inferior = palatina/lingual
    palatal_lingual: `${M},${C} ${C},${C} ${b},${b} ${a},${b}`,
    // triángulo izquierdo = distal (hemiarcada derecha) — se rota por lado
    mesial: `${M},${M} ${a},${a} ${a},${b} ${M},${C}`,
    distal: `${C},${M} ${b},${a} ${b},${b} ${C},${C}`,
    // cuadrado central = oclusal / incisal
    occlusal: `${a},${a} ${b},${a} ${b},${b} ${a},${b}`,
  };
}

function ToothCell({ code, x, y, round, surfaces, onSurfaceClick, selected }) {
  const paths = surfacePaths(round);
  const clipId = `clip-${code}`;
  const order = ["vestibular", "distal", "palatal_lingual", "mesial", "occlusal"];

  return (
    <g aria-label={`Pieza ${code}`}>
      {round && (
        <defs>
          <clipPath id={clipId}>
            <circle cx={x + C / 2} cy={y + C / 2} r={C / 2} />
          </clipPath>
        </defs>
      )}
      <g clipPath={round ? `url(#${clipId})` : undefined}>
        {order.map((surf) => {
          const st = surfaces?.[surf];
          const pts = paths[surf].split(" ")
            .map((p) => { const [px, py] = p.split(","); return `${+px + x},${+py + y}`; })
            .join(" ");
          return (
            <polygon key={surf} points={pts}
              fill={st?.color || "#ffffff"}
              stroke="#0a5c61" strokeWidth={0.8}
              style={{ cursor: "pointer" }}
              onClick={() => onSurfaceClick(code, surf)}>
              <title>{`Pieza ${code} · ${SURFACE_ES[surf]}${st?.label ? `: ${st.label}` : ""}`}</title>
            </polygon>
          );
        })}
      </g>
      {/* Borde exterior (cuadrado o círculo) */}
      {round
        ? <circle cx={x + C / 2} cy={y + C / 2} r={C / 2}
                  fill="none" stroke={selected ? "var(--petrol)" : "#0a5c61"}
                  strokeWidth={selected ? 2.5 : 1.2} />
        : <rect x={x} y={y} width={C} height={C} fill="none"
                stroke={selected ? "var(--petrol)" : "#0a5c61"}
                strokeWidth={selected ? 2.5 : 1.2} />}
    </g>
  );
}

const SURFACE_ES = {
  vestibular: "Vestibular", palatal_lingual: "Palatina/Lingual",
  mesial: "Mesial", distal: "Distal", occlusal: "Oclusal/Incisal",
};

function ToothLabel({ code, x, y }) {
  return (
    <text x={x + CELL / 2} y={y} textAnchor="middle" fontSize="11"
          fontWeight="700" fill="var(--ink)">{code}</text>
  );
}

// Casilla de recesión/movilidad (valor 1-4 o vacío)
function RMBox({ code, kind, value, x, y, onClick }) {
  return (
    <g onClick={() => onClick(code, kind)} style={{ cursor: "pointer" }}>
      <rect x={x} y={y} width={CELL} height={RM_H} rx={2}
            fill={value ? "var(--petrol-soft)" : "#ffffff"}
            stroke="#7c8a99" strokeWidth={0.8} />
      <text x={x + CELL / 2} y={y + RM_H / 2 + 3.5} textAnchor="middle"
            fontSize="10" fontWeight="600" fill="var(--ink)">
        {value || ""}
      </text>
    </g>
  );
}

export default function Odontogram({
  surfacesByTooth = {},   // { "16": { vestibular:{color,label}, ... }, ... }
  rmByTooth = {},         // { "16": { recession: 2, mobility: 1 }, ... }
  selectedTooth,
  onSurfaceClick,
  onRMClick,
}) {
  const half = 8 * (CELL + GAP) - GAP;     // ancho de una hemiarcada permanente (8 piezas)
  const totalW = half * 2 + MIDGAP;
  const cx = half + MIDGAP / 2;            // línea media

  // posición X de la pieza i dentro de una hemiarcada, alineada a la derecha
  // para grupos de menos de 8 (temporales tienen 5) para centrar bajo permanentes.
  const xInLeft = (i) => cx + MIDGAP / 2 + i * (CELL + GAP);
  const xInRight = (i, count) => {
    // hemiarcada derecha: alinear a la derecha (pegado a la línea media)
    const startFromMid = cx - MIDGAP / 2 - count * (CELL + GAP) + GAP;
    return startFromMid + i * (CELL + GAP);
  };

  // Layout vertical
  let y = 0;
  const rowRecesionTop = y; y += RM_H + 1;
  const rowMovilidadTop = y; y += RM_H + 2;
  const labelPermUpper = y; y += LABEL_H;
  const permUpperY = y; y += CELL + ARCADE_GAP;
  const tempUpperY = y; y += CELL + 6;
  const tempUpperLabelY = y; y += LABEL_H + ARCADE_GAP;
  const tempLowerLabelY = y; y += LABEL_H;
  const tempLowerY = y; y += CELL + ARCADE_GAP;
  const labelPermLowerY = y; y += LABEL_H;
  const permLowerY = y; y += CELL + 2;
  const rowMovilidadBot = y; y += RM_H + 1;
  const rowRecesionBot = y; y += RM_H;
  const totalH = y + 2;

  const surf = (code) => surfacesByTooth[code] || {};
  const rm = (code) => rmByTooth[code] || {};

  const renderPermRow = (codesR, codesL, yPos) => (
    <>
      {codesR.map((code, i) => (
        <ToothCell key={code} code={code} x={xInRight(i, 8)} y={yPos} round={false}
                   surfaces={surf(code)} selected={selectedTooth === code}
                   onSurfaceClick={onSurfaceClick} />
      ))}
      {codesL.map((code, i) => (
        <ToothCell key={code} code={code} x={xInLeft(i)} y={yPos} round={false}
                   surfaces={surf(code)} selected={selectedTooth === code}
                   onSurfaceClick={onSurfaceClick} />
      ))}
    </>
  );

  const renderTempRow = (codesR, codesL, yPos) => (
    <>
      {codesR.map((code, i) => (
        <ToothCell key={code} code={code} x={xInRight(i, 5)} y={yPos} round={true}
                   surfaces={surf(code)} selected={selectedTooth === code}
                   onSurfaceClick={onSurfaceClick} />
      ))}
      {codesL.map((code, i) => (
        <ToothCell key={code} code={code} x={xInLeft(i)} y={yPos} round={true}
                   surfaces={surf(code)} selected={selectedTooth === code}
                   onSurfaceClick={onSurfaceClick} />
      ))}
    </>
  );

  const renderLabels = (codesR, codesL, yPos, count = 8) => (
    <>
      {codesR.map((code, i) => <ToothLabel key={code} code={code} x={xInRight(i, count)} y={yPos} />)}
      {codesL.map((code, i) => <ToothLabel key={code} code={code} x={xInLeft(i)} y={yPos} />)}
    </>
  );

  const renderRM = (kind, yPos) => (
    <>
      {PERM_UPPER_R.concat().map((code, i) => (
        <RMBox key={`${kind}-${code}`} code={code} kind={kind} value={rm(code)[kind]}
               x={xInRight(i, 8)} y={yPos} onClick={onRMClick} />
      ))}
      {PERM_UPPER_L.map((code, i) => (
        <RMBox key={`${kind}-${code}`} code={code} kind={kind} value={rm(code)[kind]}
               x={xInLeft(i)} y={yPos} onClick={onRMClick} />
      ))}
    </>
  );

  const renderRMBottom = (kind, yPos) => (
    <>
      {PERM_LOWER_R.map((code, i) => (
        <RMBox key={`${kind}b-${code}`} code={code} kind={kind} value={rm(code)[kind]}
               x={xInRight(i, 8)} y={yPos} onClick={onRMClick} />
      ))}
      {PERM_LOWER_L.map((code, i) => (
        <RMBox key={`${kind}b-${code}`} code={code} kind={kind} value={rm(code)[kind]}
               x={xInLeft(i)} y={yPos} onClick={onRMClick} />
      ))}
    </>
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`-4 -4 ${totalW + 8} ${totalH + 8}`}
           style={{ width: "100%", minWidth: 680 }}
           aria-label="Odontograma MSP 033">
        {/* Recesión / Movilidad superiores (sobre permanente superior) */}
        <text x={-2} y={rowRecesionTop + RM_H / 2 + 3} fontSize="8"
              fontWeight="700" fill="var(--ink-soft)" textAnchor="end"
              transform={`translate(${totalW + 6},0)`} />
        {renderRM("recession", rowRecesionTop)}
        {renderRM("mobility", rowMovilidadTop)}
        {renderLabels(PERM_UPPER_R, PERM_UPPER_L, labelPermUpper + LABEL_H - 3)}
        {renderPermRow(PERM_UPPER_R, PERM_UPPER_L, permUpperY)}

        {/* Temporal superior */}
        {renderTempRow(TEMP_UPPER_R, TEMP_UPPER_L, tempUpperY)}
        {renderLabels(TEMP_UPPER_R, TEMP_UPPER_L, tempUpperLabelY + LABEL_H - 3, 5)}

        {/* Temporal inferior */}
        {renderLabels(TEMP_LOWER_R, TEMP_LOWER_L, tempLowerLabelY + LABEL_H - 3, 5)}
        {renderTempRow(TEMP_LOWER_R, TEMP_LOWER_L, tempLowerY)}

        {/* Permanente inferior */}
        {renderLabels(PERM_LOWER_R, PERM_LOWER_L, labelPermLowerY + LABEL_H - 3)}
        {renderPermRow(PERM_LOWER_R, PERM_LOWER_L, permLowerY)}
        {renderRMBottom("mobility", rowMovilidadBot)}
        {renderRMBottom("recession", rowRecesionBot)}

        {/* Línea media */}
        <line x1={cx} y1={permUpperY - 2} x2={cx} y2={permUpperY + CELL + 2}
              stroke="#7c8a99" strokeDasharray="3 3" />
        <line x1={cx} y1={permLowerY - 2} x2={cx} y2={permLowerY + CELL + 2}
              stroke="#7c8a99" strokeDasharray="3 3" />
      </svg>
    </div>
  );
}
