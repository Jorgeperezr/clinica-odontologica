"use client";

/**
 * Odontograma COMPACTO AVANZADO (Sprint 51).
 * ────────────────────────────────────────────────────────────────────
 * Adaptación de Dorisoy.PeriodontalChart.JavaFX. El proyecto original es
 * una aplicación de escritorio en Java/JavaFX, así que no hay código
 * reutilizable: lo que se adapta es su organización visual y su flujo de
 * trabajo, que son su verdadero aporte.
 *
 * Lo que se toma del proyecto:
 *
 *  · MATRIZ CLÍNICA. En su ficha, las columnas son dientes y las filas
 *    parámetros clínicos (PD, GM, CAL, movilidad, placa, sangrado…).
 *    Esa disposición permite recorrer UN parámetro a lo largo de toda la
 *    arcada de un vistazo, que es imposible con iconos sueltos. Aquí las
 *    filas son las cinco superficies del sistema más el estado dominante.
 *
 *  · ETIQUETAS DE FILA FIJAS a la izquierda mientras las columnas se
 *    desplazan en horizontal (su `MyScrollPane`).
 *
 *  · NOTACIÓN CON PUNTO (1.6, 2.4) junto al código FDI, como en su FXML.
 *
 *  · SEPARACIÓN POR CUADRANTES con la línea media y fondos de arcada
 *    diferenciados (`background-up` / `background-down`).
 *
 *  · MARCADOR QUE ESCALA AL ACTIVARSE: su `.circle-nerve-clicked` crece
 *    a 1.5× y cambia de relleno al hacer clic. Ese realce por escala,
 *    más legible que un simple cambio de color, se reutiliza en las
 *    celdas de superficie.
 *
 *  · SU PALETA mapeada a los tokens del sistema: azul de acción, rojo de
 *    patología, verde de salud, con sombras suaves para elevación.
 *
 * Sigue el contrato de `contract.js`: recibe datos, emite intenciones y
 * no escribe en la API. Por eso la sincronización con el odontograma
 * clásico y el 3D es estructural: los tres leen la misma fuente.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACES, SURFACE_LABELS, TEMP_LOWER_L, TEMP_LOWER_R,
  TEMP_UPPER_L, TEMP_UPPER_R, dominantState, hasRecords,
} from "./contract";
import ToothArt from "./ToothArt";

/* ── Notación con punto, como en el FXML del proyecto (1.6, 2.4…) ── */
function dotNotation(code) {
  const s = String(code);
  return `${s[0]}.${s.slice(1)}`;
}

/* ── Arcadas: cada una con su par de cuadrantes ── */
const ARCHES = [
  { key: "permUpper", label: "Arcada superior", upper: true,
    right: PERM_UPPER_R, left: PERM_UPPER_L },
  { key: "tempUpper", label: "Temporales superiores", upper: true, temp: true,
    right: TEMP_UPPER_R, left: TEMP_UPPER_L },
  { key: "tempLower", label: "Temporales inferiores", upper: false, temp: true,
    right: TEMP_LOWER_R, left: TEMP_LOWER_L },
  { key: "permLower", label: "Arcada inferior", upper: false,
    right: PERM_LOWER_R, left: PERM_LOWER_L },
];

/** Cuadrantes para la navegación rápida. */
const QUADRANTS = [
  { short: "1", label: "Superior derecho", codes: PERM_UPPER_R },
  { short: "2", label: "Superior izquierdo", codes: PERM_UPPER_L },
  { short: "3", label: "Inferior izquierdo", codes: PERM_LOWER_L },
  { short: "4", label: "Inferior derecho", codes: PERM_LOWER_R },
];

const SEQUENCE = ARCHES.flatMap((a) => [...a.right, ...a.left]);
const NAV_SURFACES = ["whole", ...SURFACES];

/* Filas de la matriz: el equivalente a sus parámetros clínicos. */
const ROWS = [
  { key: "vestibular", label: "Vestibular", short: "V" },
  { key: "mesial", label: "Mesial", short: "M" },
  { key: "occlusal", label: "Oclusal / Incisal", short: "O" },
  { key: "distal", label: "Distal", short: "D" },
  { key: "palatal_lingual", label: "Palatina / Lingual", short: "P" },
];

const COL_W = 30;      // ancho de columna por diente
const LABEL_W = 116;   // columna fija de etiquetas

/* ══════════ Celdas reutilizables ══════════ */

/**
 * Celda de superficie. El realce por ESCALA (no solo por color) viene de
 * `.circle-nerve-clicked` del proyecto original: crece y cambia de borde
 * al activarse, lo que se lee mejor de lejos en el sillón.
 */
function SurfaceCell({ code, surface, state, active, onSelect }) {
  return (
    <button type="button" role="gridcell"
            aria-selected={active}
            aria-label={`Pieza ${code}, ${SURFACE_LABELS[surface]}${state ? `: ${state.label}` : ": sin registro"}`}
            title={`${dotNotation(code)} · ${SURFACE_LABELS[surface]}${state ? ` · ${state.label}` : ""}`}
            onClick={() => onSelect(code, surface)}
            style={{
              width: COL_W - 6, height: 18, padding: 0, display: "block",
              margin: "0 auto",
              background: state?.color || "var(--elev)",
              border: active ? "2px solid var(--petrol)" : "1px solid var(--line)",
              borderRadius: 3, cursor: "pointer",
              transform: active ? "scale(1.35)" : "scale(1)",
              zIndex: active ? 2 : 1,
              position: "relative",
              boxShadow: active ? "var(--shadow)" : "none",
              transition: "transform var(--dur) var(--ease), background var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease)",
            }} />
  );
}

/** Cabecera de columna: FDI, notación con punto e ilustración. */
function ToothHeader({ code, surfaces, selected, upper, onSelect, colRef }) {
  const state = dominantState(surfaces);
  return (
    <div ref={colRef}
         style={{ width: COL_W, flexShrink: 0, textAlign: "center",
                  background: selected ? "var(--petrol-soft)" : "transparent",
                  borderRadius: 5, transition: "background var(--dur) var(--ease)" }}>
      {!upper && (
        <div style={{ lineHeight: 0, paddingBottom: 2 }}>
          <ToothArt code={code} fill={state?.color} selected={selected} size={26} />
        </div>
      )}
      <button type="button" onClick={() => onSelect(code, "whole")}
              aria-label={`Pieza ${code}, toda la pieza`}
              title={`Pieza ${dotNotation(code)} — toda la pieza`}
              className="tabular"
              style={{ width: "100%", border: "none", cursor: "pointer",
                       borderRadius: 4, padding: "1px 0", fontSize: 10.5,
                       fontWeight: 700, lineHeight: 1.25,
                       background: selected ? "var(--petrol)" : "transparent",
                       color: selected ? "var(--on-brand)" : "var(--ink)",
                       transition: "background var(--dur-fast) var(--ease)" }}>
        {code}
        <span style={{ display: "block", fontSize: 8.5, fontWeight: 500, opacity: 0.75 }}>
          {dotNotation(code)}
        </span>
      </button>
      {upper && (
        <div style={{ lineHeight: 0, paddingTop: 2 }}>
          <ToothArt code={code} fill={state?.color} selected={selected} size={26} />
        </div>
      )}
    </div>
  );
}

/** Indicador de registro por pieza (fila de resumen). */
function RecordMark({ marked, color }) {
  return (
    <span aria-hidden="true"
          style={{ display: "block", width: 8, height: 8, borderRadius: "50%",
                   margin: "0 auto",
                   background: marked ? (color || "var(--petrol)") : "transparent",
                   border: marked ? "none" : "1px solid var(--line)" }} />
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
  const [showTemp, setShowTemp] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const colRefs = useRef({});

  /* ── Cursor de navegación por teclado ── */
  const move = useCallback((axis, delta) => {
    const visibles = ARCHES.filter((a) => showTemp || !a.temp)
      .flatMap((a) => [...a.right, ...a.left]);
    if (axis === "tooth") {
      const i = visibles.indexOf(selectedTooth);
      const next = visibles[Math.max(0, Math.min(visibles.length - 1, (i === -1 ? 0 : i) + delta))];
      if (next) onSurfaceClick(next, selectedSurface || "whole");
    } else {
      const i = NAV_SURFACES.indexOf(selectedSurface || "whole");
      const next = NAV_SURFACES[(i + delta + NAV_SURFACES.length) % NAV_SURFACES.length];
      onSurfaceClick(selectedTooth || visibles[0], next);
    }
  }, [selectedTooth, selectedSurface, onSurfaceClick, showTemp]);

  useEffect(() => {
    function onKey(e) {
      const t = e.target;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const acciones = {
        ArrowRight: () => move("tooth", 1),
        ArrowLeft: () => move("tooth", -1),
        ArrowDown: () => move("surface", 1),
        ArrowUp: () => move("surface", -1),
        Enter: () => selectedTooth && setQuickOpen(true),
        Escape: () => setQuickOpen(false),
      };
      const fn = acciones[e.key];
      if (fn) { e.preventDefault(); fn(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, selectedTooth]);

  /* ── Desplazamiento inteligente hacia la pieza activa ── */
  useEffect(() => {
    const el = selectedTooth && colRefs.current[selectedTooth];
    if (el?.scrollIntoView) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }, [selectedTooth, zoom]);

  const resumen = useMemo(() => {
    const con = SEQUENCE.filter((c) => hasRecords(surfacesByTooth[c])).length;
    return { con, total: SEQUENCE.length };
  }, [surfacesByTooth]);

  const selSurfaces = selectedTooth ? surfacesByTooth[selectedTooth] : null;
  const arcadas = ARCHES.filter((a) => showTemp || !a.temp);

  /** Franja de columnas de un cuadrante. */
  const columnas = (codes, upper) => codes.map((code) => (
    <ToothHeader key={code} code={code} surfaces={surfacesByTooth[code]}
                 selected={selectedTooth === code} upper={upper}
                 onSelect={onSurfaceClick}
                 colRef={(el) => { colRefs.current[code] = el; }} />
  ));

  /** Fila de celdas de una superficie para un grupo de piezas. */
  const filaSuperficie = (codes, rowKey) => codes.map((code) => (
    <div key={code} style={{ width: COL_W, flexShrink: 0, padding: "2px 0" }}>
      <SurfaceCell code={code} surface={rowKey}
                   state={surfacesByTooth[code]?.[rowKey]}
                   active={selectedTooth === code && selectedSurface === rowKey}
                   onSelect={onSurfaceClick} />
    </div>
  ));

  return (
    <div>
      {/* ── Barra de control ── */}
      <div style={{ display: "flex", gap: 10, alignItems: "center",
                    flexWrap: "wrap", marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
                       textTransform: "uppercase", color: "var(--ink-faint)" }}>
          Cuadrante
        </span>
        <div style={{ display: "flex", gap: 3 }}>
          {QUADRANTS.map((q) => (
            <button key={q.short} type="button" className="btn btn-ghost" title={q.label}
                    onClick={() => onSurfaceClick(q.codes[0], "whole")}
                    style={{ fontSize: 12, padding: "3px 11px" }}>
              {q.short}
            </button>
          ))}
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5,
                        color: "var(--ink-soft)" }}>
          <input type="checkbox" checked={showTemp}
                 onChange={(e) => setShowTemp(e.target.checked)} />
          Dentición temporal
        </label>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
            {resumen.con}/{resumen.total} con registro
          </span>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12,
                          color: "var(--ink-soft)" }}>
            Zoom
            <input type="range" min="1" max="2.4" step="0.1" value={zoom}
                   onChange={(e) => setZoom(Number(e.target.value))}
                   aria-label="Nivel de zoom" style={{ width: 84 }} />
            <span className="tabular" style={{ minWidth: 30 }}>{zoom.toFixed(1)}×</span>
          </label>
        </div>
      </div>

      <div style={{ display: "grid", gap: 14,
                    gridTemplateColumns: selectedTooth ? "minmax(0,1fr) 268px" : "1fr" }}>
        {/* ── Matriz clínica ── */}
        <div style={{ border: "1px solid var(--line)", borderRadius: "var(--radius)",
                      background: "var(--card)", overflow: "hidden" }}>
          <div style={{ overflowX: "auto", overflowY: "hidden" }}>
            <div style={{ transform: `scale(${zoom})`, transformOrigin: "top left",
                          transition: "transform var(--dur) var(--ease)",
                          width: `${100 * zoom}%` }}>
              {arcadas.map((arch) => (
                <div key={arch.key}
                     style={{ borderBottom: "1px solid var(--line)",
                              // Fondos de arcada diferenciados, como background-up/down
                              background: arch.upper
                                ? "linear-gradient(180deg, var(--petrol-soft) 0%, transparent 60%)"
                                : "linear-gradient(0deg, var(--petrol-soft) 0%, transparent 60%)" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".06em",
                                textTransform: "uppercase", color: "var(--ink-faint)",
                                padding: "5px 10px 2px" }}>
                    {arch.label}
                  </div>

                  {/* Filas: etiqueta fija + columnas desplazables */}
                  {(() => {
                    const cabecera = (
                      <div key="head" style={{ display: "flex", alignItems: "flex-end" }}>
                        <div style={{ width: LABEL_W, flexShrink: 0, position: "sticky", left: 0,
                                      background: "var(--card)", zIndex: 3,
                                      fontSize: 10.5, fontWeight: 700, color: "var(--ink-faint)",
                                      padding: "2px 8px", textTransform: "uppercase",
                                      letterSpacing: ".05em" }}>
                          Pieza
                        </div>
                        {columnas(arch.right, arch.upper)}
                        <div aria-hidden="true"
                             style={{ width: 10, alignSelf: "stretch",
                                      borderLeft: "1px dashed var(--line-strong)", flexShrink: 0 }} />
                        {columnas(arch.left, arch.upper)}
                      </div>
                    );
                    const filas = ROWS.map((row) => (
                      <div key={row.key} style={{ display: "flex", alignItems: "center" }}>
                        <div style={{ width: LABEL_W, flexShrink: 0, position: "sticky", left: 0,
                                      background: "var(--card)", zIndex: 3,
                                      display: "flex", alignItems: "center", gap: 6,
                                      fontSize: 11.5, color: "var(--ink-soft)",
                                      padding: "2px 8px" }}>
                          <span className="tabular"
                                style={{ fontWeight: 700, color: "var(--petrol)", width: 12 }}>
                            {row.short}
                          </span>
                          {row.label}
                        </div>
                        {filaSuperficie(arch.right, row.key)}
                        <div aria-hidden="true"
                             style={{ width: 10, alignSelf: "stretch",
                                      borderLeft: "1px dashed var(--line-strong)", flexShrink: 0 }} />
                        {filaSuperficie(arch.left, row.key)}
                      </div>
                    ));
                    const resumenFila = (
                      <div key="sum" style={{ display: "flex", alignItems: "center",
                                              paddingBottom: 6 }}>
                        <div style={{ width: LABEL_W, flexShrink: 0, position: "sticky", left: 0,
                                      background: "var(--card)", zIndex: 3,
                                      fontSize: 11.5, color: "var(--ink-soft)", padding: "2px 8px" }}>
                          Registro
                        </div>
                        {[...arch.right].map((code) => (
                          <div key={code} style={{ width: COL_W, flexShrink: 0 }}>
                            <RecordMark marked={hasRecords(surfacesByTooth[code])}
                                        color={dominantState(surfacesByTooth[code])?.color} />
                          </div>
                        ))}
                        <div aria-hidden="true" style={{ width: 10, flexShrink: 0 }} />
                        {[...arch.left].map((code) => (
                          <div key={code} style={{ width: COL_W, flexShrink: 0 }}>
                            <RecordMark marked={hasRecords(surfacesByTooth[code])}
                                        color={dominantState(surfacesByTooth[code])?.color} />
                          </div>
                        ))}
                      </div>
                    );
                    // En la arcada superior la cabecera va arriba; en la inferior, abajo
                    return arch.upper
                      ? [cabecera, ...filas, resumenFila]
                      : [resumenFila, ...filas, cabecera];
                  })()}
                </div>
              ))}
            </div>
          </div>
          <p style={{ fontSize: 11.5, color: "var(--ink-faint)", padding: "8px 10px", margin: 0 }}>
            Clic en una celda registra sobre esa superficie · flechas ← → recorren piezas ·
            ↑ ↓ cambian de superficie · Enter abre el registro rápido
          </p>
        </div>

        {/* ── Panel contextual ── */}
        {selectedTooth && (
          <aside className="card animate-rise" style={{ alignSelf: "start" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>Pieza {selectedTooth}</h3>
              <span className="tabular" style={{ fontSize: 12, color: "var(--ink-faint)" }}>
                {dotNotation(selectedTooth)}
              </span>
            </div>
            <span className="badge badge-warn" style={{ marginBottom: 12, display: "inline-flex" }}>
              {SURFACE_LABELS[selectedSurface] || "Toda la pieza"}
            </span>

            {selSurfaces && Object.keys(selSurfaces).length > 0 ? (
              <div style={{ display: "grid", gap: 5, marginBottom: 12 }}>
                {Object.entries(selSurfaces).map(([surf, st]) => (
                  <button key={surf} type="button"
                          onClick={() => onSurfaceClick(selectedTooth, surf)}
                          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5,
                                   background: "transparent", border: "none", cursor: "pointer",
                                   padding: "3px 0", textAlign: "left" }}>
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

            {typeof onQuickRegister === "function" && states.length > 0 && (
              <>
                <button className="btn btn-primary" style={{ width: "100%", fontSize: 13 }}
                        onClick={() => setQuickOpen((v) => !v)}>
                  {quickOpen ? "Cerrar registro rápido" : "Registro rápido"}
                </button>
                {quickOpen && (
                  <div className="animate-rise"
                       style={{ marginTop: 10, maxHeight: 250, overflowY: "auto",
                                display: "grid", gap: 4 }}>
                    {states.map((s) => (
                      <button key={s.id} type="button"
                              onClick={() => {
                                // Coordenadas explícitas: no depende de estado asíncrono
                                onQuickRegister(s.id, selectedTooth, selectedSurface || "whole");
                                setQuickOpen(false);
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
