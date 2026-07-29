"use client";

/**
 * Odontograma COMPACTO AVANZADO (Sprint 50).
 * ────────────────────────────────────────────────────────────────────
 * Adaptación de la arquitectura visual de PeriodontalCharting (proyecto
 * iOS/SwiftUI) al sistema. No se copió código —era Swift— sino los
 * patrones de interacción que hacen útil ese tipo de ficha:
 *
 *  · ToothColumnView  → cada pieza es una COLUMNA de celdas apilables,
 *                       en vez de un icono suelto. Permite leer varias
 *                       dimensiones clínicas de una pieza de un vistazo.
 *  · QuadrantView     → cuadrantes con etiquetas laterales (V/P) y
 *                       navegación directa por cuadrante.
 *  · ChartingCursor   → cursor con teclado: las flechas recorren piezas
 *                       y superficies sin soltar el ratón, que es lo que
 *                       acelera el registro en una consulta real.
 *  · ZoomableScroll   → zoom de 1× a 3× con desplazamiento automático
 *                       de la pieza activa al centro del visor.
 *  · NumberPadPopover → edición rápida en un popover junto a la celda,
 *                       sin abandonar el contexto.
 *
 * Sigue el contrato de `contract.js`: recibe datos, emite intenciones y
 * no escribe en la API. `states` y `onQuickRegister` son opcionales; si
 * el contenedor no los pasa, el popover simplemente no ofrece registro
 * directo y la vista continúa funcionando.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACES, SURFACE_LABELS, TEMP_LOWER_L, TEMP_LOWER_R,
  TEMP_UPPER_L, TEMP_UPPER_R, dominantState, hasRecords,
} from "../contract";
import ToothArt from "../ToothArt";

/* ── Cuadrantes: orden clínico y etiquetas ── */
const QUADRANTS = [
  { key: "q1", label: "Sup. der.", short: "1", codes: PERM_UPPER_R, upper: true },
  { key: "q2", label: "Sup. izq.", short: "2", codes: PERM_UPPER_L, upper: true },
  { key: "q5", label: "Temp. sup. der.", short: "5", codes: TEMP_UPPER_R, upper: true, temp: true },
  { key: "q6", label: "Temp. sup. izq.", short: "6", codes: TEMP_UPPER_L, upper: true, temp: true },
  { key: "q8", label: "Temp. inf. der.", short: "8", codes: TEMP_LOWER_R, upper: false, temp: true },
  { key: "q7", label: "Temp. inf. izq.", short: "7", codes: TEMP_LOWER_L, upper: false, temp: true },
  { key: "q4", label: "Inf. der.", short: "4", codes: PERM_LOWER_R, upper: false },
  { key: "q3", label: "Inf. izq.", short: "3", codes: PERM_LOWER_L, upper: false },
];

/** Orden de recorrido del cursor: todas las piezas en secuencia clínica. */
const SEQUENCE = QUADRANTS.flatMap((q) => q.codes);
const NAV_SURFACES = ["whole", ...SURFACES];

/* ══════════ Celdas reutilizables ══════════ */

/** Celda de superficie: la unidad direccionable (pieza, superficie). */
function SurfaceCell({ code, surface, state, active, onSelect, size = 15 }) {
  return (
    <button type="button" role="gridcell"
            aria-label={`Pieza ${code}, ${SURFACE_LABELS[surface]}${state ? `: ${state.label}` : ""}`}
            aria-selected={active}
            title={`${SURFACE_LABELS[surface]}${state ? ` · ${state.label}` : ""}`}
            onClick={(e) => { e.stopPropagation(); onSelect(code, surface); }}
            style={{
              width: size, height: size, padding: 0,
              background: state?.color || "var(--elev)",
              border: active ? "2px solid var(--petrol)" : "1px solid var(--line)",
              borderRadius: 3, cursor: "pointer",
              transition: "background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease)",
            }} />
  );
}

/** Cruz de superficies: disposición anatómica (V arriba, P abajo, M/D a los lados). */
function SurfaceCross({ code, surfaces, selectedSurface, isSelected, onSelect }) {
  const cell = (surf) => (
    <SurfaceCell code={code} surface={surf} state={surfaces?.[surf]}
                 active={isSelected && selectedSurface === surf} onSelect={onSelect} />
  );
  return (
    <div role="grid" aria-label={`Superficies de la pieza ${code}`}
         style={{ display: "grid", gridTemplateColumns: "repeat(3, auto)",
                  gap: 2, justifyContent: "center" }}>
      <span /> {cell("vestibular")} <span />
      {cell("distal")} {cell("occlusal")} {cell("mesial")}
      <span /> {cell("palatal_lingual")} <span />
    </div>
  );
}

/** Indicador booleano: marca si la pieza tiene algún registro. */
function RecordDot({ marked }) {
  return (
    <span aria-hidden="true"
          style={{ width: 6, height: 6, borderRadius: "50%",
                   background: marked ? "var(--petrol)" : "transparent",
                   border: marked ? "none" : "1px solid var(--line)" }} />
  );
}

/** Columna de una pieza: número, ilustración, cruz de superficies e indicador. */
function ToothColumn({
  code, surfaces, upper, isSelected, selectedSurface, onSelect, cellRef,
}) {
  const state = dominantState(surfaces);
  const num = (
    <button type="button" onClick={() => onSelect(code, "whole")}
            className="tabular"
            aria-label={`Pieza ${code}, toda la pieza`}
            style={{
              border: "none", cursor: "pointer", borderRadius: 4,
              padding: "1px 5px", fontSize: 11, fontWeight: 700,
              background: isSelected ? "var(--petrol)" : "transparent",
              color: isSelected ? "var(--on-brand)" : "var(--ink)",
              transition: "background var(--dur-fast) var(--ease)",
            }}>
      {code}
    </button>
  );
  const art = <ToothArt code={code} fill={state?.color} selected={isSelected} size={30} />;
  const cross = (
    <SurfaceCross code={code} surfaces={surfaces} selectedSurface={selectedSurface}
                  isSelected={isSelected} onSelect={onSelect} />
  );
  const dot = <RecordDot marked={hasRecords(surfaces)} />;

  // Arriba: número → diente → cruz. Abajo: espejo, como en la boca.
  const stack = upper ? [num, art, cross, dot] : [dot, cross, art, num];

  return (
    <div ref={cellRef}
         style={{ display: "flex", flexDirection: "column", alignItems: "center",
                  gap: 3, width: 54, flexShrink: 0,
                  padding: "4px 2px", borderRadius: 6,
                  background: isSelected ? "var(--petrol-soft)" : "transparent",
                  transition: "background var(--dur) var(--ease)" }}>
      {stack.map((el, i) => <div key={i} style={{ lineHeight: 0 }}>{el}</div>)}
    </div>
  );
}

/* ══════════ Vista principal ══════════ */

export default function AdvancedCompactView({
  surfacesByTooth = {},
  selectedTooth,
  selectedSurface,
  onSurfaceClick,
  states = [],
  onQuickRegister,
}) {
  const [zoom, setZoom] = useState(1);
  const [popover, setPopover] = useState(false);
  const viewportRef = useRef(null);
  const cellRefs = useRef({});

  /* ── Cursor de navegación (adaptado de ChartingCursor) ──
     Recorre piezas y superficies con el teclado. La lógica de qué se
     registra sigue en el contenedor; aquí solo se mueve la selección. */
  const move = useCallback((axis, delta) => {
    const seqIdx = SEQUENCE.indexOf(selectedTooth);
    if (axis === "tooth") {
      const next = SEQUENCE[Math.max(0, Math.min(SEQUENCE.length - 1,
        (seqIdx === -1 ? 0 : seqIdx) + delta))];
      if (next) onSurfaceClick(next, selectedSurface || "whole");
    } else {
      const i = NAV_SURFACES.indexOf(selectedSurface || "whole");
      const next = NAV_SURFACES[(i + delta + NAV_SURFACES.length) % NAV_SURFACES.length];
      onSurfaceClick(selectedTooth || SEQUENCE[0], next);
    }
  }, [selectedTooth, selectedSurface, onSurfaceClick]);

  useEffect(() => {
    function onKey(e) {
      // No secuestrar el teclado mientras se escribe en un campo
      const t = e.target;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const map = {
        ArrowRight: () => move("tooth", 1),
        ArrowLeft: () => move("tooth", -1),
        ArrowDown: () => move("surface", 1),
        ArrowUp: () => move("surface", -1),
        Enter: () => selectedTooth && setPopover(true),
        Escape: () => setPopover(false),
      };
      const fn = map[e.key];
      if (fn) { e.preventDefault(); fn(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, selectedTooth]);

  /* ── Desplazamiento inteligente: la pieza activa entra en vista ── */
  useEffect(() => {
    if (!selectedTooth) return;
    const el = cellRefs.current[selectedTooth];
    if (el?.scrollIntoView) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [selectedTooth, zoom]);

  const jumpToQuadrant = useCallback((q) => {
    onSurfaceClick(q.codes[0], "whole");
  }, [onSurfaceClick]);

  const resumen = useMemo(() => {
    const conRegistro = Object.keys(surfacesByTooth).filter(
      (c) => hasRecords(surfacesByTooth[c])).length;
    return { conRegistro, total: SEQUENCE.length };
  }, [surfacesByTooth]);

  const selSurfaces = selectedTooth ? surfacesByTooth[selectedTooth] : null;

  return (
    <div>
      {/* ── Barra de control: cuadrantes y zoom ── */}
      <div style={{ display: "flex", gap: 10, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
                       textTransform: "uppercase", color: "var(--ink-faint)" }}>
          Cuadrante
        </span>
        <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
          {QUADRANTS.filter((q) => !q.temp).map((q) => (
            <button key={q.key} type="button" onClick={() => jumpToQuadrant(q)}
                    className="btn btn-ghost" title={q.label}
                    style={{ fontSize: 12, padding: "3px 10px" }}>
              {q.short}
            </button>
          ))}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
            {resumen.conRegistro}/{resumen.total} con registro
          </span>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12,
                          color: "var(--ink-soft)" }}>
            Zoom
            <input type="range" min="1" max="3" step="0.1" value={zoom}
                   onChange={(e) => setZoom(Number(e.target.value))}
                   aria-label="Nivel de zoom" style={{ width: 90 }} />
            <span className="tabular" style={{ minWidth: 30 }}>{zoom.toFixed(1)}×</span>
          </label>
          {zoom !== 1 && (
            <button className="btn btn-ghost" style={{ fontSize: 12, padding: "3px 10px" }}
                    onClick={() => setZoom(1)}>Restablecer</button>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gap: 14,
                    gridTemplateColumns: selectedTooth ? "minmax(0,1fr) 260px" : "1fr" }}>
        {/* ── Visor con zoom y desplazamiento ── */}
        <div>
          <div ref={viewportRef}
               style={{ overflow: "auto", border: "1px solid var(--line)",
                        borderRadius: "var(--radius)", background: "var(--card)",
                        padding: 12, maxHeight: 520 }}>
            <div style={{ transform: `scale(${zoom})`, transformOrigin: "top center",
                          transition: "transform var(--dur) var(--ease)",
                          width: zoom > 1 ? `${100 / zoom}%` : "100%" }}>
              {/* Arcadas: permanentes y temporales, con línea media */}
              {[["q1", "q2"], ["q5", "q6"], ["q8", "q7"], ["q4", "q3"]].map(([r, l], idx) => {
                const qr = QUADRANTS.find((q) => q.key === r);
                const ql = QUADRANTS.find((q) => q.key === l);
                return (
                  <div key={idx}
                       style={{ display: "flex", justifyContent: "center",
                                alignItems: "flex-start", gap: 10, marginBottom: 10 }}>
                    <div style={{ display: "flex", gap: 2 }}>
                      {qr.codes.map((code) => (
                        <ToothColumn key={code} code={code} upper={qr.upper}
                                     surfaces={surfacesByTooth[code]}
                                     isSelected={selectedTooth === code}
                                     selectedSurface={selectedSurface}
                                     onSelect={onSurfaceClick}
                                     cellRef={(el) => { cellRefs.current[code] = el; }} />
                      ))}
                    </div>
                    <div aria-hidden="true"
                         style={{ width: 1, alignSelf: "stretch", background: "var(--line)" }} />
                    <div style={{ display: "flex", gap: 2 }}>
                      {ql.codes.map((code) => (
                        <ToothColumn key={code} code={code} upper={ql.upper}
                                     surfaces={surfacesByTooth[code]}
                                     isSelected={selectedTooth === code}
                                     selectedSurface={selectedSurface}
                                     onSelect={onSurfaceClick}
                                     cellRef={(el) => { cellRefs.current[code] = el; }} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 6 }}>
            Flechas ← → recorren piezas · ↑ ↓ cambian de superficie · Enter abre el registro rápido
          </p>
        </div>

        {/* ── Panel lateral: pieza activa y registro rápido ── */}
        {selectedTooth && (
          <aside className="card animate-rise" style={{ alignSelf: "start" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>Pieza {selectedTooth}</h3>
              <span className="badge badge-warn" style={{ marginLeft: "auto" }}>
                {SURFACE_LABELS[selectedSurface] || "Toda la pieza"}
              </span>
            </div>

            {/* Estado por superficie */}
            {selSurfaces && Object.keys(selSurfaces).length > 0 ? (
              <div style={{ display: "grid", gap: 5, marginBottom: 12 }}>
                {Object.entries(selSurfaces).map(([surf, st]) => (
                  <button key={surf} type="button"
                          onClick={() => onSurfaceClick(selectedTooth, surf)}
                          style={{ display: "flex", alignItems: "center", gap: 8,
                                   fontSize: 12.5, background: "transparent", cursor: "pointer",
                                   border: "none", padding: "3px 0", textAlign: "left" }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, flexShrink: 0,
                                   background: st.color, border: "1px solid var(--line)" }} />
                    <span style={{ color: "var(--ink-soft)" }}>
                      {SURFACE_LABELS[surf] || surf}
                    </span>
                    <span style={{ marginLeft: "auto", fontWeight: 600 }}>{st.label}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 12.5, color: "var(--ink-faint)", marginBottom: 12 }}>
                Sin registros en esta pieza.
              </p>
            )}

            {/* Registro rápido: la paleta clínica completa del sistema */}
            {typeof onQuickRegister === "function" && states.length > 0 && (
              <>
                <button className="btn btn-primary" style={{ width: "100%", fontSize: 13 }}
                        onClick={() => setPopover((v) => !v)}>
                  {popover ? "Cerrar registro rápido" : "Registro rápido"}
                </button>
                {popover && (
                  <div className="animate-rise"
                       style={{ marginTop: 10, maxHeight: 240, overflowY: "auto",
                                display: "grid", gap: 4 }}>
                    {states.map((s) => (
                      <button key={s.id} type="button"
                              onClick={() => {
                                // Se envían pieza y superficie explícitas para no
                                // depender de estado asíncrono del contenedor.
                                onQuickRegister(s.id, selectedTooth, selectedSurface || "whole");
                                setPopover(false);
                              }}
                              style={{ display: "flex", alignItems: "center", gap: 8,
                                       padding: "6px 8px", borderRadius: 6, fontSize: 12.5,
                                       background: "transparent", border: "1px solid var(--line)",
                                       cursor: "pointer", textAlign: "left" }}>
                        <span style={{ width: 12, height: 12, borderRadius: 3, flexShrink: 0,
                                       background: s.color, border: "1px solid var(--line)" }} />
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
