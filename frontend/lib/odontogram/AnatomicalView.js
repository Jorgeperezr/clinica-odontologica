"use client";

/**
 * Modelo ANATÓMICO (Sprint 46, ilustrado en Sprint 47 y redibujado
 * después como lámina de atlas).
 *
 * Se lee como una ficha anatómica impresa: cada pieza en vista
 * vestibular —corona y raíces a escala real— y en vista oclusal, con
 * sus cúspides y surcos. Las coronas superiores e inferiores se
 * encuentran en el plano oclusal, como en la boca.
 *
 * La vista oclusal ES la rueda de superficies de antes: las mismas
 * cinco regiones pulsables, ahora con la forma real de la pieza y con
 * mesial mirando a la línea media en cada cuadrante (la rueda anterior
 * lo ponía siempre a la derecha, lo que en los cuadrantes 2 y 3 dejaba
 * mesial y distal cambiados respecto al dibujo).
 *
 * Se compone en HTML (una celda por pieza) en vez de un único SVG: cada
 * diente es un objetivo táctil independiente y la fila se desplaza sola
 * en pantallas estrechas.
 *
 * Cumple el contrato de `contract.js`: solo dibuja y emite intenciones.
 */

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  TEMP_LOWER_L, TEMP_LOWER_R, TEMP_UPPER_L, TEMP_UPPER_R,
  dominantState,
} from "./contract";
import { ALTO_OCLUSAL, VistaOclusal, VistaVestibular, medidas } from "./AnatomiaDental";
import { isUpper } from "./ToothArt";

/**
 * Píxeles por milímetro. Con 5, la arcada permanente ocupa unos 700 px
 * de ancho, y el incisivo inferior —la pieza más estrecha— sigue dando
 * un objetivo de unos 25 px.
 */
const ESCALA = 5;
const ANCHO_MINIMO = 24;

/** Celda: vista vestibular, vista oclusal y número, en espejo según la arcada. */
function ToothCell({ code, temporal, surfaces, selectedTooth, selectedSurface, onSurfaceClick }) {
  const selected = selectedTooth === code;
  const up = isUpper(code);
  const state = dominantState(surfaces);
  const ancho = Math.max(medidas(code).w * ESCALA, ANCHO_MINIMO);
  const altoOclusal = ALTO_OCLUSAL[temporal ? "temporal" : "permanente"] * ESCALA;

  const vestibular = (
    <VistaVestibular code={code} estado={state} seleccionado={selected} escala={ESCALA}
                     onClick={() => onSurfaceClick(code, "whole")} />
  );
  const oclusal = (
    // Alto fijo por fila para que los números queden alineados aunque
    // un molar sea el doble de grueso que un incisivo; la pieza se pega
    // al lado de su vista vestibular.
    <div style={{ height: altoOclusal, display: "flex", alignItems: up ? "flex-start" : "flex-end" }}>
      <VistaOclusal code={code} surfaces={surfaces} selected={selected}
                    selectedSurface={selectedSurface} escala={ESCALA} onClick={onSurfaceClick} />
    </div>
  );
  const num = (
    <button type="button" onClick={() => onSurfaceClick(code, "whole")}
            className="tabular"
            aria-label={`Pieza ${code}: seleccionar toda la pieza`}
            style={{ background: "none", border: "none", padding: "1px 4px", cursor: "pointer",
                     fontSize: 11.5, fontWeight: 700, borderRadius: 4, lineHeight: 1.3,
                     color: selected ? "var(--on-brand)" : "var(--ink)",
                     backgroundColor: selected ? "var(--petrol)" : "transparent" }}>
      {code}
    </button>
  );

  // Superior: raíces arriba, corona, cara oclusal y número hacia el plano
  // oclusal. Inferior: el mismo orden reflejado.
  const orden = up ? [vestibular, oclusal, num] : [num, oclusal, vestibular];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                  gap: 4, width: ancho, flex: "none" }}>
      {orden.map((el, i) => <div key={i} style={{ lineHeight: 0 }}>{el}</div>)}
    </div>
  );
}

function Arch({ right, left, temporal, ...rest }) {
  const row = (codes, lado) => (
    <div style={{ display: "flex", gap: 2, justifyContent: lado === "d" ? "flex-end" : "flex-start",
                  flex: 1 }}>
      {codes.map((code) => (
        <ToothCell key={code} code={code} temporal={temporal}
                   surfaces={rest.surfacesByTooth[code]} {...rest} />
      ))}
    </div>
  );
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "stretch", gap: 10 }}>
      {row(right, "d")}
      <div style={{ width: 1, background: "var(--line)" }} aria-hidden="true" />
      {row(left, "i")}
    </div>
  );
}

export default function AnatomicalView({
  surfacesByTooth = {}, selectedTooth, selectedSurface, onSurfaceClick,
}) {
  const shared = { surfacesByTooth, selectedTooth, selectedSurface, onSurfaceClick };
  return (
    <div style={{ overflowX: "auto", paddingBottom: 4 }}>
      <div style={{ display: "grid", gap: 14, minWidth: 740 }}>
        <Arch right={PERM_UPPER_R} left={PERM_UPPER_L} {...shared} />
        <Arch right={TEMP_UPPER_R} left={TEMP_UPPER_L} temporal {...shared} />
        {/* Plano oclusal: aquí se encuentran las dos arcadas. */}
        <div style={{ height: 1, background: "var(--line-strong)", margin: "2px 0" }} aria-hidden="true" />
        <Arch right={TEMP_LOWER_R} left={TEMP_LOWER_L} temporal {...shared} />
        <Arch right={PERM_LOWER_R} left={PERM_LOWER_L} {...shared} />
      </div>
    </div>
  );
}
