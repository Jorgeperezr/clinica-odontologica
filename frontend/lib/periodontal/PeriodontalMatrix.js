"use client";

/**
 * Odontograma compacto avanzado / Ficha periodontal (Sprint 52).
 * ────────────────────────────────────────────────────────────────────
 * Implementación completa de la organización visual de
 * Dorisoy.PeriodontalChart.JavaFX, con las filas de su ficha:
 *
 *   Presente · Implante · Movilidad · Furcación · Sangrado · Placa ·
 *   Ancho de encía · Margen gingival · Profundidad de sondaje
 *
 * más las filas de ESTADOS CLÍNICOS por superficie del sistema, que es
 * lo que mantiene la sincronización con el odontograma clásico y el 3D.
 *
 * ── Nota de arquitectura ──
 * Este componente es un HÍBRIDO deliberado y es el único de los cuatro
 * modelos que no es un renderizador puro:
 *
 *   · Los ESTADOS por superficie llegan por props desde `OdontogramTab`
 *     y se registran con sus callbacks. Sincronización estructural
 *     intacta: registrar aquí se ve en el clásico y en el 3D.
 *   · Las MEDICIONES periodontales son datos nuevos que ningún otro
 *     modelo posee, así que este componente gestiona su propia carga y
 *     guardado contra `periodontal-exams` / `periodontal-teeth`.
 *
 * Esa separación es intencional: mezclar mediciones de sondaje en la
 * tabla de estados obligaría a que un registro de caries tuviera
 * columnas de profundidad. Al vivir aparte, la arquitectura queda
 * preparada para periodontograma, ortodoncia e implantología como capas
 * adicionales sobre las mismas piezas.
 *
 * El guardado es diferido (450 ms desde la última tecla) para que
 * escribir una serie de sondajes no genere una petición por dígito.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import {
  PERM_LOWER_L, PERM_LOWER_R, PERM_UPPER_L, PERM_UPPER_R,
  SURFACE_LABELS,
} from "../odontogram/contract";
import ToothArt from "../odontogram/ToothArt";
import {
  CELL_W, FurcationMark, GradeSelect, ImplantCheck, PresenceSwitch,
  SiteFlagRow, SiteNumberRow, SurfaceStateCell,
} from "./cells";

const LABEL_W = 132;

/** Notación con punto (1.6), como en el FXML del proyecto. */
const dot = (code) => `${String(code)[0]}.${String(code).slice(1)}`;

/* Arcadas con sus dos cuadrantes; la línea media los separa. */
const ARCHES = [
  { key: "sup", label: "Superior", upper: true, right: PERM_UPPER_R, left: PERM_UPPER_L },
  { key: "inf", label: "Inferior", upper: false, right: PERM_LOWER_R, left: PERM_LOWER_L },
];
const SEQUENCE = ARCHES.flatMap((a) => [...a.right, ...a.left]);

/* Superficies del sistema, como filas de la matriz. */
const SURFACE_ROWS = [
  ["vestibular", "V"], ["mesial", "M"], ["occlusal", "O"],
  ["distal", "D"], ["palatal_lingual", "P"],
];

export default function AdvancedCompactView({
  // Estados clínicos (compartidos con el clásico y el 3D)
  surfacesByTooth = {},
  selectedTooth,
  selectedSurface,
  onSurfaceClick,
  states = [],
  onQuickRegister,
  // Identificador del paciente para la capa periodontal
  patientId,
}) {
  const [exam, setExam] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [activeSite, setActiveSite] = useState(null);
  const [quickOpen, setQuickOpen] = useState(false);
  const colRefs = useRef({});
  const pending = useRef({});   // { toothId: {campo: valor} } por guardar
  const timer = useRef(null);

  /* ── Carga de la exploración periodontal ── */
  const load = useCallback(async () => {
    if (!patientId) { setLoading(false); return; }
    setLoading(true); setError("");
    try {
      const resp = await api(`/patients/${patientId}/periodontal-exams/`);
      if (!resp.ok) throw new Error(`No se pudo cargar la ficha (error ${resp.status}).`);
      const data = await resp.json();
      const filas = data.results || data;
      setExam(filas.length > 0 ? filas[0] : null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  async function crearExploracion() {
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/periodontal-exams/`, {
        method: "POST",
        body: JSON.stringify({ date: new Date().toISOString().slice(0, 10) }),
      });
      if (!resp.ok) throw new Error(`No se pudo crear la ficha (error ${resp.status}).`);
      setExam(await resp.json());
    } catch (err) { setError(err.message); }
  }

  /* ── Guardado diferido ──
     Se acumulan los cambios por pieza y se envían 450 ms después de la
     última edición: escribir seis sondajes produce una petición, no seis. */
  const flush = useCallback(async () => {
    const lote = pending.current;
    pending.current = {};
    const ids = Object.keys(lote);
    if (ids.length === 0) return;
    setSaving(true);
    try {
      await Promise.all(ids.map((id) =>
        api(`/periodontal-teeth/${id}/`, { method: "PATCH", body: JSON.stringify(lote[id]) })));
      // Se recarga para traer derivados y estadísticas recalculadas
      const resp = await api(`/patients/${patientId}/periodontal-exams/`);
      if (resp.ok) {
        const data = await resp.json();
        const filas = data.results || data;
        if (filas.length > 0) setExam(filas[0]);
      }
    } catch {
      setError("No se pudieron guardar algunos cambios.");
    } finally {
      setSaving(false);
    }
  }, [patientId]);

  const queue = useCallback((toothId, cambios) => {
    pending.current[toothId] = { ...(pending.current[toothId] || {}), ...cambios };
    // Actualización optimista: la matriz responde al instante
    setExam((prev) => prev && ({
      ...prev,
      teeth: prev.teeth.map((t) => (t.id === toothId ? { ...t, ...cambios } : t)),
    }));
    clearTimeout(timer.current);
    timer.current = setTimeout(flush, 450);
  }, [flush]);

  useEffect(() => () => clearTimeout(timer.current), []);

  /* ── Índice de piezas por código FDI ── */
  const byCode = useMemo(() => {
    const map = {};
    (exam?.teeth || []).forEach((t) => { map[t.tooth_code] = t; });
    return map;
  }, [exam]);

  /* ── Cursor de teclado ── */
  useEffect(() => {
    function onKey(e) {
      const t = e.target;
      if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      const i = SEQUENCE.indexOf(selectedTooth);
      const acciones = {
        ArrowRight: () => onSurfaceClick(SEQUENCE[Math.min(SEQUENCE.length - 1, (i < 0 ? -1 : i) + 1)], selectedSurface || "whole"),
        ArrowLeft: () => onSurfaceClick(SEQUENCE[Math.max(0, (i < 0 ? 1 : i) - 1)], selectedSurface || "whole"),
        ArrowDown: () => {
          const s = SURFACE_ROWS.map((r) => r[0]);
          const k = s.indexOf(selectedSurface);
          onSurfaceClick(selectedTooth || SEQUENCE[0], s[(k + 1 + s.length) % s.length]);
        },
        ArrowUp: () => {
          const s = SURFACE_ROWS.map((r) => r[0]);
          const k = s.indexOf(selectedSurface);
          onSurfaceClick(selectedTooth || SEQUENCE[0], s[(k - 1 + s.length) % s.length]);
        },
        Enter: () => selectedTooth && setQuickOpen(true),
        Escape: () => setQuickOpen(false),
      };
      const fn = acciones[e.key];
      if (fn) { e.preventDefault(); fn(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedTooth, selectedSurface, onSurfaceClick]);

  /* ── Desplazamiento inteligente ── */
  useEffect(() => {
    const el = selectedTooth && colRefs.current[selectedTooth];
    el?.scrollIntoView?.({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [selectedTooth, zoom]);

  /* ── Constructores de fila ── */
  const rowLabel = (texto, sigla) => (
    <div style={{ width: LABEL_W, flexShrink: 0, position: "sticky", left: 0, zIndex: 3,
                  background: "var(--card)", display: "flex", alignItems: "center", gap: 6,
                  fontSize: 11, color: "var(--ink-soft)", padding: "1px 8px",
                  borderRight: "1px solid var(--line)" }}>
      {sigla && <span className="tabular" style={{ fontWeight: 700, color: "var(--petrol)", width: 11 }}>{sigla}</span>}
      {texto}
    </div>
  );

  const midline = (
    <div aria-hidden="true" style={{ width: 9, alignSelf: "stretch", flexShrink: 0,
                                     borderLeft: "1px dashed var(--line-strong)" }} />
  );

  /** Aplica `render` a cada pieza de un cuadrante. */
  const cells = (codes, render) => codes.map((code) => (
    <div key={code} style={{ width: CELL_W + 8, flexShrink: 0, padding: "1px 0" }}>
      {render(code, byCode[code])}
    </div>
  ));

  const editable = Boolean(exam);

  /* ── Filas periodontales ── */
  function perioRows(codes) {
    const flag = (t, campo, idx) => {
      if (!t) return;
      const arr = [...(t[campo] || [false, false, false, false, false, false])];
      arr[idx] = !arr[idx];
      queue(t.id, { [campo]: arr });
    };
    const num = (t, campo, idx, valor) => {
      if (!t) return;
      const arr = [...(t[campo] || [0, 0, 0, 0, 0, 0])];
      const n = Math.max(-10, Math.min(20, Number(valor) || 0));
      arr[idx] = n;
      queue(t.id, { [campo]: arr });
    };
    return [
      { key: "present", label: "Presente", render: (code, t) => t && (
        <PresenceSwitch on={t.is_present} label={`Pieza ${code} presente`}
                        onToggle={() => queue(t.id, { is_present: !t.is_present })} /> ) },
      { key: "implant", label: "Implante", render: (code, t) => t && (
        <ImplantCheck on={t.has_implant} disabled={!t.is_present}
                      label={`Implante en ${code}`}
                      onToggle={() => queue(t.id, { has_implant: !t.has_implant })} /> ) },
      { key: "mobility", label: "Movilidad", render: (code, t) => t && (
        <GradeSelect value={t.mobility} disabled={!t.is_present}
                     label={`Movilidad de ${code}`}
                     onChange={(v) => queue(t.id, { mobility: v })} /> ) },
      { key: "furc", label: "Furcación", render: (code, t) => t && (
        <FurcationMark grade={t.furcation_buccal} disabled={!t.is_present}
                       label={`Furcación de ${code}`}
                       onCycle={() => queue(t.id, { furcation_buccal: (t.furcation_buccal + 1) % 4 })} /> ) },
      { key: "bop_b", label: "Sangrado (V)", render: (code, t) => t && (
        <SiteFlagRow values={t.bleeding} base={0} color="var(--red)" disabled={!t.is_present}
                     label={`Sangrado vestibular de ${code}`}
                     onToggle={(i) => flag(t, "bleeding", i)} /> ) },
      { key: "pl_b", label: "Placa (V)", render: (code, t) => t && (
        <SiteFlagRow values={t.plaque} base={0} color="var(--petrol)" disabled={!t.is_present}
                     label={`Placa vestibular de ${code}`}
                     onToggle={(i) => flag(t, "plaque", i)} /> ) },
      { key: "gm_b", label: "Margen ging. (V)", render: (code, t) => t && (
        <SiteNumberRow values={t.gingival_margin} base={0} disabled={!t.is_present}
                       label={`Margen gingival vestibular de ${code}`}
                       activeSite={selectedTooth === code ? activeSite : null}
                       onFocusSite={(i) => { setActiveSite(i); onSurfaceClick(code, "vestibular"); }}
                       onChange={(i, v) => num(t, "gingival_margin", i, v)} /> ) },
      { key: "pd_b", label: "Sondaje (V)", render: (code, t) => t && (
        <SiteNumberRow values={t.probing_depth} base={0} disabled={!t.is_present}
                       label={`Sondaje vestibular de ${code}`}
                       activeSite={selectedTooth === code ? activeSite : null}
                       onFocusSite={(i) => { setActiveSite(i); onSurfaceClick(code, "vestibular"); }}
                       onChange={(i, v) => num(t, "probing_depth", i, v)} /> ) },
      { key: "pd_l", label: "Sondaje (P/L)", render: (code, t) => t && (
        <SiteNumberRow values={t.probing_depth} base={3} disabled={!t.is_present}
                       label={`Sondaje palatino de ${code}`}
                       activeSite={selectedTooth === code ? activeSite : null}
                       onFocusSite={(i) => { setActiveSite(i); onSurfaceClick(code, "palatal_lingual"); }}
                       onChange={(i, v) => num(t, "probing_depth", i, v)} /> ) },
      { key: "gm_l", label: "Margen ging. (P/L)", render: (code, t) => t && (
        <SiteNumberRow values={t.gingival_margin} base={3} disabled={!t.is_present}
                       label={`Margen gingival palatino de ${code}`}
                       activeSite={selectedTooth === code ? activeSite : null}
                       onFocusSite={(i) => { setActiveSite(i); onSurfaceClick(code, "palatal_lingual"); }}
                       onChange={(i, v) => num(t, "gingival_margin", i, v)} /> ) },
      { key: "pl_l", label: "Placa (P/L)", render: (code, t) => t && (
        <SiteFlagRow values={t.plaque} base={3} color="var(--petrol)" disabled={!t.is_present}
                     label={`Placa palatina de ${code}`}
                     onToggle={(i) => flag(t, "plaque", i)} /> ) },
      { key: "bop_l", label: "Sangrado (P/L)", render: (code, t) => t && (
        <SiteFlagRow values={t.bleeding} base={3} color="var(--red)" disabled={!t.is_present}
                     label={`Sangrado palatino de ${code}`}
                     onToggle={(i) => flag(t, "bleeding", i)} /> ) },
    ];
  }

  const stats = exam?.statistics;

  return (
    <div>
      {/* ── Barra de control ── */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap",
                    marginBottom: 10 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".05em",
                       textTransform: "uppercase", color: "var(--ink-faint)" }}>Cuadrante</span>
        <div style={{ display: "flex", gap: 3 }}>
          {[["1", PERM_UPPER_R], ["2", PERM_UPPER_L], ["3", PERM_LOWER_L], ["4", PERM_LOWER_R]]
            .map(([n, codes]) => (
              <button key={n} type="button" className="btn btn-ghost"
                      onClick={() => onSurfaceClick(codes[0], "whole")}
                      style={{ fontSize: 12, padding: "3px 11px" }}>{n}</button>
            ))}
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          {saving && <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>Guardando…</span>}
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12,
                          color: "var(--ink-soft)" }}>
            Zoom
            <input type="range" min="1" max="2.2" step="0.1" value={zoom}
                   onChange={(e) => setZoom(Number(e.target.value))}
                   aria-label="Nivel de zoom" style={{ width: 84 }} />
            <span className="tabular" style={{ minWidth: 30 }}>{zoom.toFixed(1)}×</span>
          </label>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* Sin exploración creada aún */}
      {!loading && !exam && (
        <div className="card" style={{ marginBottom: 14, textAlign: "center" }}>
          <p style={{ fontSize: 13.5, color: "var(--ink-soft)", marginBottom: 10 }}>
            Este paciente no tiene ficha periodontal. Los estados clínicos por
            superficie se muestran igual; crea una ficha para registrar sondaje,
            margen gingival, placa, sangrado, movilidad y furcación.
          </p>
          <button className="btn btn-primary" onClick={crearExploracion}>
            Crear ficha periodontal
          </button>
        </div>
      )}

      <div style={{ display: "grid", gap: 14,
                    gridTemplateColumns: selectedTooth ? "minmax(0,1fr) 262px" : "1fr" }}>
        {/* ── Matriz ── */}
        <div style={{ border: "1px solid var(--line)", borderRadius: "var(--radius)",
                      background: "var(--card)", overflow: "hidden" }}>
          {loading ? (
            <div className="empty">Cargando ficha…</div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <div style={{ transform: `scale(${zoom})`, transformOrigin: "top left",
                            transition: "transform var(--dur) var(--ease)",
                            width: `${100 * zoom}%` }}>
                {ARCHES.map((arch) => {
                  const filasPerio = editable ? perioRows() : [];
                  const cabecera = (
                    <div key="head" style={{ display: "flex", alignItems: "flex-end",
                                             background: "var(--petrol-soft)" }}>
                      {rowLabel(arch.label)}
                      {[arch.right, arch.left].map((codes, ci) => (
                        <div key={ci} style={{ display: "flex" }}>
                          {ci === 1 && midline}
                          {codes.map((code) => (
                            <div key={code} ref={(el) => { colRefs.current[code] = el; }}
                                 style={{ width: CELL_W + 8, flexShrink: 0, textAlign: "center",
                                          background: selectedTooth === code ? "var(--petrol-soft)" : "transparent" }}>
                              {!arch.upper && (
                                <div style={{ lineHeight: 0 }}>
                                  <ToothArt code={code} size={24}
                                            fill={surfacesByTooth[code]?.occlusal?.color}
                                            selected={selectedTooth === code} />
                                </div>
                              )}
                              <button type="button" onClick={() => onSurfaceClick(code, "whole")}
                                      className="tabular" aria-label={`Pieza ${code}`}
                                      title={`Pieza ${dot(code)}`}
                                      style={{ width: "100%", border: "none", cursor: "pointer",
                                               borderRadius: 3, padding: "1px 0", fontSize: 10,
                                               fontWeight: 700, lineHeight: 1.2,
                                               background: selectedTooth === code ? "var(--petrol)" : "transparent",
                                               color: selectedTooth === code ? "var(--on-brand)" : "var(--ink)" }}>
                                {code}
                                <span style={{ display: "block", fontSize: 8, fontWeight: 500, opacity: .7 }}>
                                  {dot(code)}
                                </span>
                              </button>
                              {arch.upper && (
                                <div style={{ lineHeight: 0 }}>
                                  <ToothArt code={code} size={24}
                                            fill={surfacesByTooth[code]?.occlusal?.color}
                                            selected={selectedTooth === code} />
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  );

                  const fila = (key, label, sigla, render) => (
                    <div key={key} style={{ display: "flex", alignItems: "center",
                                            borderTop: "1px solid var(--line)" }}>
                      {rowLabel(label, sigla)}
                      {cells(arch.right, render)}
                      {midline}
                      {cells(arch.left, render)}
                    </div>
                  );

                  const filasEstado = SURFACE_ROWS.map(([surf, sigla]) =>
                    fila(`st-${surf}`, SURFACE_LABELS[surf], sigla, (code) => (
                      <SurfaceStateCell code={code} surface={surf}
                                        surfaceLabel={SURFACE_LABELS[surf]}
                                        state={surfacesByTooth[code]?.[surf]}
                                        active={selectedTooth === code && selectedSurface === surf}
                                        onSelect={onSurfaceClick} />
                    )));

                  const filasMedicion = filasPerio.map((r) =>
                    fila(r.key, r.label, null, r.render));

                  return (
                    <div key={arch.key} style={{ borderBottom: "2px solid var(--line-strong)" }}>
                      {arch.upper
                        ? [cabecera, ...filasEstado, ...filasMedicion]
                        : [...filasMedicion, ...filasEstado, cabecera]}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Índices agregados, como el pie de la ficha original */}
          {stats && (
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap",
                          padding: "10px 12px", borderTop: "1px solid var(--line)",
                          background: "var(--paper)", fontSize: 12.5 }}>
              {[["Sondaje medio", `${stats.mean_probing_depth} mm`],
                ["Nivel de inserción medio", `${stats.mean_attachment_level} mm`],
                ["Placa", `${stats.plaque_percent} %`],
                ["Sangrado al sondaje", `${stats.bleeding_percent} %`],
                ["Sitios evaluados", stats.sites]].map(([k, v]) => (
                <span key={k} style={{ display: "inline-flex", gap: 6 }}>
                  <span style={{ color: "var(--ink-soft)" }}>{k}:</span>
                  <strong className="tabular">{v}</strong>
                </span>
              ))}
            </div>
          )}

          <p style={{ fontSize: 11.5, color: "var(--ink-faint)", padding: "8px 12px", margin: 0 }}>
            Clic en una celda de estado registra sobre esa superficie · flechas ← → recorren
            piezas · ↑ ↓ cambian de superficie · Enter abre el registro rápido
          </p>
        </div>

        {/* ── Panel contextual ── */}
        {selectedTooth && (
          <aside className="card animate-rise" style={{ alignSelf: "start" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>Pieza {selectedTooth}</h3>
              <span className="tabular" style={{ fontSize: 12, color: "var(--ink-faint)" }}>
                {dot(selectedTooth)}
              </span>
            </div>
            <span className="badge badge-warn" style={{ marginBottom: 12, display: "inline-flex" }}>
              {SURFACE_LABELS[selectedSurface] || "Toda la pieza"}
            </span>

            {/* Mediciones periodontales de la pieza */}
            {byCode[selectedTooth] && (
              <div style={{ marginBottom: 12, fontSize: 12.5 }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".05em",
                              textTransform: "uppercase", color: "var(--ink-faint)",
                              marginBottom: 5 }}>Periodontal</div>
                {[["Sondaje", byCode[selectedTooth].probing_depth],
                  ["Margen gingival", byCode[selectedTooth].gingival_margin],
                  ["Nivel de inserción", byCode[selectedTooth].attachment_level]].map(([k, arr]) => (
                  <div key={k} style={{ display: "flex", gap: 6, marginBottom: 2 }}>
                    <span style={{ color: "var(--ink-soft)" }}>{k}:</span>
                    <span className="tabular" style={{ marginLeft: "auto" }}>
                      {(arr || []).join(" · ")}
                    </span>
                  </div>
                ))}
                <div style={{ display: "flex", gap: 6 }}>
                  <span style={{ color: "var(--ink-soft)" }}>Movilidad:</span>
                  <span className="tabular" style={{ marginLeft: "auto" }}>
                    {byCode[selectedTooth].mobility}
                  </span>
                </div>
              </div>
            )}

            {/* Estados clínicos registrados */}
            <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".05em",
                          textTransform: "uppercase", color: "var(--ink-faint)",
                          marginBottom: 5 }}>Estados</div>
            {surfacesByTooth[selectedTooth] && Object.keys(surfacesByTooth[selectedTooth]).length > 0 ? (
              <div style={{ display: "grid", gap: 4, marginBottom: 12 }}>
                {Object.entries(surfacesByTooth[selectedTooth]).map(([surf, st]) => (
                  <button key={surf} type="button"
                          onClick={() => onSurfaceClick(selectedTooth, surf)}
                          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5,
                                   background: "transparent", border: "none", cursor: "pointer",
                                   padding: "2px 0", textAlign: "left" }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, flexShrink: 0,
                                   background: st.color, border: "1px solid var(--line)" }} />
                    <span style={{ color: "var(--ink-soft)" }}>{SURFACE_LABELS[surf] || surf}</span>
                    <span style={{ marginLeft: "auto", fontWeight: 600 }}>{st.label}</span>
                  </button>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: 12.5, color: "var(--ink-faint)", marginBottom: 12 }}>
                Sin estados registrados.
              </p>
            )}

            {typeof onQuickRegister === "function" && states.length > 0 && (
              <>
                <button className="btn btn-primary" style={{ width: "100%", fontSize: 13 }}
                        onClick={() => setQuickOpen((v) => !v)}>
                  {quickOpen ? "Cerrar registro rápido" : "Registro rápido"}
                </button>
                {quickOpen && (
                  <div className="animate-rise" style={{ marginTop: 10, maxHeight: 230,
                                                         overflowY: "auto", display: "grid", gap: 4 }}>
                    {states.map((s) => (
                      <button key={s.id} type="button"
                              onClick={() => {
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
