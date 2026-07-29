"use client";

/**
 * Modelo ANATÓMICO (Sprint 46, ilustrado en Sprint 47).
 *
 * Cada pieza se dibuja con su ilustración anatómica real —corona con
 * cúspides y surcos, raíces según el cuadrante— acompañada de una rueda
 * de cinco superficies para el registro preciso. La arcada inferior se
 * refleja, de modo que la boca se lee como se ve en el sillón.
 *
 * Se compone en HTML (una celda por pieza) en vez de un único SVG: cada
 * diente es entonces un objetivo táctil independiente, y la rejilla se
 * reordena sola en tablet sin recalcular coordenadas.
 *
 * Cumple el contrato de `contract.js`: solo dibuja y emite intenciones.
 */

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACES, TEMP_LOWER_L, TEMP_LOWER_R, TEMP_UPPER_L, TEMP_UPPER_R,
  dominantState,
} from "./contract";
import ToothArt, { isUpper } from "./ToothArt";

const WHEEL = 34;

/** Rueda de cinco superficies: cuatro cuadrantes y centro oclusal. */
function SurfaceWheel({ code, surfaces, selectedSurface, selected, onClick }) {
  const r = WHEEL / 2, c = WHEEL / 2, inner = r * 0.44;
  const p = (a, rad) => [c + rad * Math.cos(a), c + rad * Math.sin(a)];
  const quad = (a0, a1) => {
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
    <svg width={WHEEL} height={WHEEL} viewBox={`0 0 ${WHEEL} ${WHEEL}`}
         aria-label={`Superficies de la pieza ${code}`}>
      {SURFACES.filter((s) => s !== "occlusal").map((s) => {
        const on = selected && selectedSurface === s;
        return (
          <path key={s} d={geom[s]}
                fill={surfaces?.[s]?.color || "var(--elev)"}
                stroke={on ? "var(--petrol)" : "var(--line-strong)"}
                strokeWidth={on ? 1.8 : 0.8}
                onClick={(e) => { e.stopPropagation(); onClick(code, s); }}
                style={{ cursor: "pointer" }}>
            <title>{`Pieza ${code} — ${s}`}</title>
          </path>
        );
      })}
      <circle cx={c} cy={c} r={inner}
              fill={surfaces?.occlusal?.color || "var(--elev)"}
              stroke={(selected && selectedSurface === "occlusal") ? "var(--petrol)" : "var(--line-strong)"}
              strokeWidth={(selected && selectedSurface === "occlusal") ? 1.8 : 0.8}
              onClick={(e) => { e.stopPropagation(); onClick(code, "occlusal"); }}
              style={{ cursor: "pointer" }}>
        <title>{`Pieza ${code} — oclusal`}</title>
      </circle>
    </svg>
  );
}

/** Celda: ilustración + número + rueda, ordenados según la arcada. */
function ToothCell({ code, surfaces, selectedTooth, selectedSurface, onSurfaceClick }) {
  const selected = selectedTooth === code;
  const up = isUpper(code);
  const state = dominantState(surfaces);

  const art = (
    <ToothArt code={code} fill={state?.color} selected={selected} size={56}
              title={`Pieza ${code}${state?.label ? ` — ${state.label}` : ""}`}
              onClick={() => onSurfaceClick(code, "whole")} />
  );
  const num = (
    <button type="button" onClick={() => onSurfaceClick(code, "whole")}
            className="tabular"
            style={{ background: "none", border: "none", padding: "1px 4px", cursor: "pointer",
                     fontSize: 11.5, fontWeight: 700, borderRadius: 4,
                     color: selected ? "var(--on-brand)" : "var(--ink)",
                     backgroundColor: selected ? "var(--petrol)" : "transparent" }}>
      {code}
    </button>
  );
  const wheel = (
    <SurfaceWheel code={code} surfaces={surfaces} selected={selected}
                  selectedSurface={selectedSurface} onClick={onSurfaceClick} />
  );

  // Superior: diente arriba, número, rueda. Inferior: espejo vertical.
  const orden = up ? [art, num, wheel] : [wheel, num, art];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                  gap: 3, minWidth: 46 }}>
      {orden.map((el, i) => <div key={i} style={{ lineHeight: 0 }}>{el}</div>)}
    </div>
  );
}

function Arch({ right, left, ...rest }) {
  const row = (codes) => (
    <div style={{ display: "flex", gap: 3 }}>
      {codes.map((code) => (
        <ToothCell key={code} code={code} surfaces={rest.surfacesByTooth[code]} {...rest} />
      ))}
    </div>
  );
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "flex-start", gap: 14 }}>
      {row(right)}
      <div style={{ width: 1, alignSelf: "stretch", background: "var(--line)" }} aria-hidden="true" />
      {row(left)}
    </div>
  );
}

export default function AnatomicalView({
  surfacesByTooth = {}, selectedTooth, selectedSurface, onSurfaceClick,
}) {
  const shared = { surfacesByTooth, selectedTooth, selectedSurface, onSurfaceClick };
  return (
    <div style={{ overflowX: "auto", paddingBottom: 4 }}>
      <div style={{ display: "grid", gap: 18, minWidth: 720 }}>
        <Arch right={PERM_UPPER_R} left={PERM_UPPER_L} {...shared} />
        <Arch right={TEMP_UPPER_R} left={TEMP_UPPER_L} {...shared} />
        <Arch right={TEMP_LOWER_R} left={TEMP_LOWER_L} {...shared} />
        <Arch right={PERM_LOWER_R} left={PERM_LOWER_L} {...shared} />
      </div>
    </div>
  );
}
