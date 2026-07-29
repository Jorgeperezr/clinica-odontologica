"use client";

/**
 * Modelo COMPACTO (Sprint 46).
 *
 * Cuadrícula por cuadrantes en HTML —no SVG— pensada para pantallas
 * pequeñas y para revisión rápida: cada pieza es un botón con una franja
 * por superficie, de modo que se ve de un vistazo qué está registrado
 * sin necesidad de ampliar. Al seleccionar una pieza aparecen sus cinco
 * superficies como botones grandes, cómodos en táctil.
 *
 * Cumple el contrato de `contract.js`: solo dibuja y emite intenciones.
 */

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACES, SURFACE_LABELS, TEMP_LOWER_L, TEMP_LOWER_R,
  TEMP_UPPER_L, TEMP_UPPER_R, hasRecords,
} from "./contract";

function ToothChip({ code, surfaces, selected, onClick }) {
  const marked = hasRecords(surfaces);
  return (
    <button type="button" onClick={() => onClick(code, "whole")}
            title={`Pieza ${code}`}
            style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 3,
              padding: "6px 4px 5px", minWidth: 42,
              background: selected ? "var(--petrol-soft)" : "var(--elev)",
              border: `1px solid ${selected ? "var(--petrol)" : "var(--line)"}`,
              borderRadius: 8, cursor: "pointer",
              transition: "background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease)",
            }}>
      {/* Cinco franjas: una por superficie */}
      <span style={{ display: "flex", gap: 1.5, height: 12 }} aria-hidden="true">
        {SURFACES.map((s) => (
          <span key={s} style={{
            width: 4, height: "100%", borderRadius: 1,
            background: surfaces?.[s]?.color || "var(--line)",
          }} />
        ))}
      </span>
      <span className="tabular" style={{
        fontSize: 12, fontWeight: marked ? 700 : 500,
        color: selected ? "var(--petrol)" : "var(--ink)",
      }}>{code}</span>
    </button>
  );
}

function Quadrant({ title, codes, surfacesByTooth, selectedTooth, onClick }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
                    textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
        {codes.map((code) => (
          <ToothChip key={code} code={code} surfaces={surfacesByTooth[code]}
                     selected={selectedTooth === code} onClick={onClick} />
        ))}
      </div>
    </div>
  );
}

export default function CompactView({
  surfacesByTooth = {}, selectedTooth, selectedSurface, onSurfaceClick,
}) {
  const quadrants = [
    ["Superior derecho", PERM_UPPER_R], ["Superior izquierdo", PERM_UPPER_L],
    ["Temporal superior der.", TEMP_UPPER_R], ["Temporal superior izq.", TEMP_UPPER_L],
    ["Temporal inferior der.", TEMP_LOWER_R], ["Temporal inferior izq.", TEMP_LOWER_L],
    ["Inferior derecho", PERM_LOWER_R], ["Inferior izquierdo", PERM_LOWER_L],
  ];

  return (
    <div>
      <div style={{ display: "grid", gap: 16,
                    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        {quadrants.map(([title, codes]) => (
          <Quadrant key={title} title={title} codes={codes}
                    surfacesByTooth={surfacesByTooth}
                    selectedTooth={selectedTooth} onClick={onSurfaceClick} />
        ))}
      </div>

      {/* Selección de superficie: botones grandes, cómodos en táctil */}
      {selectedTooth && (
        <div className="animate-rise"
             style={{ marginTop: 16, padding: "12px 14px", borderRadius: 10,
                      background: "var(--petrol-soft)", border: "1px solid var(--petrol)" }}>
          <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8 }}>
            Pieza {selectedTooth} · elige la superficie
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {["whole", ...SURFACES].map((s) => (
              <button key={s} type="button"
                      onClick={() => onSurfaceClick(selectedTooth, s)}
                      className={`btn ${selectedSurface === s ? "btn-primary" : "btn-ghost"}`}
                      style={{ fontSize: 12.5 }}>
                {SURFACE_LABELS[s]}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
