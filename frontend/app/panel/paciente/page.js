"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, currentUser } from "../../../lib/api";
import BackButton from "../../../lib/BackButton";
import PatientPayments from "../../../lib/PatientPayments";
import { VIEWS, getView, readPreferredView, savePreferredView } from "../../../lib/odontogram/registry";
import Form033Panel from "../../../lib/Form033Panel";
import DiagnosisSection from "../../../lib/DiagnosisTab";
import CpoCeoCard from "../../../lib/CpoCeoCard";
import OralHealthIndicators from "../../../lib/OralHealthIndicators";
import OdontogramLegend from "../../../lib/OdontogramLegend";
import ExamRequestsSection from "../../../lib/ExamRequestsSection";
import { useConfirm } from "../../../lib/ConfirmDialog";
import { ConsentsTab, DocumentsTab, PlanTab } from "../../../lib/ClinicalTabs";


const SURFACE_NAMES = {
  whole: "Toda la pieza", vestibular: "Vestibular", palatal_lingual: "Palatina/Lingual",
  mesial: "Mesial", distal: "Distal", occlusal: "Oclusal/Incisal",
};

export default function PatientDetailPage() {
  return (
    <Suspense fallback={<div className="empty">Cargando…</div>}>
      <PatientDetail />
    </Suspense>
  );
}

function PatientDetail() {
  const id = useSearchParams().get("id");
  const [patient, setPatient] = useState(null);
  const [role, setRole] = useState("");
  const [tab, setTab] = useState("odontograma");

  useEffect(() => {
    (async () => {
      try { const u = await currentUser(); setRole(u?.role || ""); } catch { /* opcional */ }
    })();
  }, []);

  useEffect(() => {
    api(`/patients/${id}/`).then(async (r) => setPatient(await r.json())).catch(() => {});
  }, [id]);

  if (!patient) return <div className="empty">Cargando…</div>;

  return (
    <div>
      <BackButton fallback="/panel/pacientes/" label="Pacientes" />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", margin: "8px 0 4px" }}>
        <h1 style={{ fontSize: 24 }}>{patient.full_name}</h1>
        <span className="tabular" style={{ color: "var(--ink-soft)", fontSize: 14 }}>
          CI {patient.national_id} {patient.phone ? `· ${patient.phone}` : ""}
        </span>
      </div>

      <div className="tabs" style={{ display: "flex", gap: 4, margin: "16px 0 20px", borderBottom: "1px solid var(--line)" }}>
        {[["odontograma", "Odontograma"], ["evoluciones", "Evoluciones"],
          ["plan", "Plan de tratamiento"], ["documentos", "Documentos"],
          ["consentimientos", "Consentimientos"],
          ["odontograma3d", "Odontograma 3D"],
          ...(["admin", "reception"].includes(role) ? [["cobros", "Cobros"]] : [])].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            style={{
              padding: "9px 16px", border: "none", background: "transparent",
              fontWeight: 600, fontSize: 14,
              color: tab === key ? "var(--petrol)" : "var(--ink-soft)",
              borderBottom: tab === key ? "3px solid var(--petrol)" : "3px solid transparent",
            }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "odontograma" && <OdontogramTab patientId={id} />}
      {tab === "evoluciones" && <EvolutionsTab patientId={id} />}
      {tab === "plan" && <PlanTab patientId={id} />}
      {tab === "documentos" && (
        <>
          <ExamRequestsSection patientId={id} />
          <DocumentsTab patientId={id} />
        </>
      )}
      {tab === "consentimientos" && <ConsentsTab patientId={id} />}
      {tab === "odontograma3d" && <OdontogramTab patientId={id} initialView="tridimensional" />}
      {tab === "cobros" && <PatientPayments patientId={id} role={role} />}
    </div>
  );
}

/* ───────────────────────── Odontograma ───────────────────────── */

function OdontogramTab({ patientId, initialView }) {
  const [confirm, ConfirmUI] = useConfirm();
  const [toothNotes, setToothNotes] = useState("");
  const [states, setStates] = useState([]);       // catálogo de estados
  const [teeth, setTeeth] = useState({});          // { "16": { vestibular:{color,label}, ... } }
  const [rm, setRm] = useState({});                // { "16": { recession, mobility } }
  const [selected, setSelected] = useState(null);  // pieza seleccionada
  const [selectedSurface, setSelectedSurface] = useState("whole"); // superficie activa
  const [viewKey, setViewKey] = useState("clasico");
  const [rmEdit, setRmEdit] = useState(null);      // { code, kind } en edición
  const [pendingReg, setPendingReg] = useState(null); // { stateId, label } desde la simbología

  useEffect(() => { setViewKey(initialView || readPreferredView()); }, [initialView]);
  const [history, setHistory] = useState([]);      // historial de la pieza
  const [error, setError] = useState("");

  const loadCurrent = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/odontogram/current/`);
      const data = await resp.json();
      const map = {};       // por pieza y superficie
      const rmMap = {};     // recesión/movilidad por pieza
      for (const t of data.teeth || []) {
        const code = t.tooth_fdi_code;
        if (!map[code]) map[code] = {};
        // "whole" pinta las 5 superficies; una superficie concreta pinta solo esa
        if (t.surface === "whole") {
          for (const s of ["vestibular", "palatal_lingual", "mesial", "distal", "occlusal"]) {
            if (!map[code][s]) map[code][s] = { color: t.state_color, label: t.state_label };
          }
        } else if (!map[code][t.surface]) {
          map[code][t.surface] = { color: t.state_color, label: t.state_label };
        }
        if (t.mobility != null || t.recession != null) {
          rmMap[code] = {
            mobility: t.mobility ?? rmMap[code]?.mobility,
            recession: t.recession ?? rmMap[code]?.recession,
          };
        }
      }
      setTeeth(map);
      setRm(rmMap);
    } catch { setError("No se pudo cargar el odontograma."); }
  }, [patientId]);

  useEffect(() => {
    loadCurrent();
    api("/odontogram-states/").then(async (r) => setStates(await r.json())).catch(() => {});
  }, [loadCurrent]);

  const loadHistory = useCallback(async (tooth) => {
    try {
      const resp = await api(`/patients/${patientId}/tooth-records/?tooth_fdi_code=${tooth}`);
      const data = await resp.json();
      setHistory(data.results || data);
    } catch { /* silencioso */ }
  }, [patientId]);

  function handleSurfaceClick(code, surface) {
    setSelected(code);
    setSelectedSurface(surface);
    loadHistory(code);
  }

  // Recesión/movilidad: clic en la casilla abre un editor inline (sin
  // diálogos del navegador). El valor se guarda como ToothRecord de la
  // pieza con el campo numérico correspondiente.
  function handleRMClick(code, kind) {
    setRmEdit({ code, kind });
    setError("");
  }

  async function saveRM(num) {
    if (!rmEdit) return;
    const { code, kind } = rmEdit;
    const label = kind === "recession" ? "recesión" : "movilidad";
    try {
      const sano = states.find((s) => s.code === "SANO")?.id || states[0]?.id;
      const resp = await api(`/patients/${patientId}/tooth-records/`, {
        method: "POST",
        body: JSON.stringify({
          tooth_fdi_code: code, surface: "whole", state: sano,
          [kind]: num, date: new Date().toISOString().slice(0, 10),
          notes: `Registro de ${label}: ${num ?? "—"}`,
        }),
      });
      if (!resp.ok) throw new Error(`No se pudo guardar la ${label} (error ${resp.status}).`);
      setRmEdit(null);
      await loadCurrent();
    } catch (err) { setError(err.message); }
  }

  async function deleteRecord(rec) {
    const ok = await confirm({
      title: `Eliminar registro de la pieza ${rec.tooth_fdi_code}`,
      message: `Se eliminará "${rec.state_label}" (${rec.date}).\nEsta acción corrige un registro erróneo y queda auditada.`,
      confirmLabel: "Eliminar",
      danger: true,
    });
    if (!ok) return;
    setError("");
    try {
      const resp = await api(`/tooth-records/${rec.id}/`, { method: "DELETE" });
      if (!resp.ok && resp.status !== 204) throw new Error(`No se pudo eliminar (error ${resp.status}).`);
      await loadCurrent();
      await loadHistory(selected);
    } catch (err) { setError(err.message); }
  }

  // Nuevo flujo (Sprint 32): el símbolo de la leyenda abre un mini-formulario
  // con la superficie autodetectada; guardar registra de inmediato.
  function handleLegendSelect(state) {
    if (!selected) {
      setError("Selecciona primero una pieza o superficie en el odontograma.");
      return;
    }
    setError("");
    setPendingReg({ stateId: state.id, label: state.label, color: state.color });
  }

  async function registerState(stateId, override = {}) {
    setError("");
    const tooth = override.tooth ?? selected;
    const surface = override.surface ?? selectedSurface;
    const notes = override.notes ?? toothNotes;
    try {
      const resp = await api(`/patients/${patientId}/tooth-records/`, {
        method: "POST",
        body: JSON.stringify({
          tooth_fdi_code: tooth,
          surface: surface,
          state: stateId,
          notes: notes,
          date: new Date().toISOString().slice(0, 10),
        }),
      });
      if (!resp.ok) {
        let msg = `No se pudo registrar el estado (error ${resp.status}).`;
        try {
          const data = await resp.json();
          msg = data?.error?.message || data?.detail || msg;
        } catch { /* respuesta no-JSON */ }
        throw new Error(msg);
      }
      await loadCurrent();
      await loadHistory(tooth);
      setToothNotes("");
      setPendingReg(null);
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      <Form033Panel patientId={patientId} />
      <OralHealthIndicators patientId={patientId} />
      <CpoCeoCard patientId={patientId} refreshKey={Object.keys(teeth).length} />
      <DiagnosisSection patientId={patientId} />
      {error && <div className="error-box">{error}</div>}

      <div className="card" style={{ marginBottom: 18 }}>
        {/* Selector de modelo. Los tres son vistas de los MISMOS datos:
            reciben las mismas props y emiten las mismas intenciones, así
            que registrar en uno se refleja al instante en los otros. */}
        <div style={{ display: initialView ? "none" : "flex", alignItems: "center", gap: 8,
                      marginBottom: 12, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: ".05em",
                         textTransform: "uppercase", color: "var(--ink-faint)" }}>
            Modelo
          </span>
          <div role="radiogroup" aria-label="Modelo de odontograma"
               style={{ display: "inline-flex", gap: 2, padding: 3,
                        background: "var(--paper)", borderRadius: 999,
                        border: "1px solid var(--line)" }}>
            {VIEWS.map((v) => (
              <button key={v.key} type="button" role="radio"
                      aria-checked={viewKey === v.key} title={v.description}
                      onClick={() => { setViewKey(v.key); savePreferredView(v.key); }}
                      style={{
                        padding: "5px 12px", borderRadius: 999, border: "none",
                        fontSize: 12.5, fontWeight: 600, cursor: "pointer",
                        background: viewKey === v.key ? "var(--petrol)" : "transparent",
                        color: viewKey === v.key ? "var(--on-brand)" : "var(--ink-soft)",
                        transition: "background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease)",
                      }}>
                {v.label}
              </button>
            ))}
          </div>
        </div>

        {(() => {
          const View = getView(viewKey).Component;
          return (
            <View surfacesByTooth={teeth} rmByTooth={rm}
                  selectedTooth={selected} selectedSurface={selectedSurface}
                  onSurfaceClick={handleSurfaceClick}
                  onRMClick={handleRMClick}
                  history={history}
                  patientId={patientId}
                  states={states}
                  onQuickRegister={(stateId, tooth, surface) =>
                    registerState(stateId, {
                      tooth: tooth ?? selected,
                      surface: surface ?? selectedSurface,
                      notes: "",
                    })} />
          );
        })()}
        {selected && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10,
                        flexWrap: "wrap", fontSize: 13.5 }}>
            <span style={{ fontWeight: 700, color: "var(--petrol)" }}>
              Pieza {selected} · {SURFACE_NAMES[selectedSurface] || selectedSurface}
            </span>
            {selectedSurface !== "whole" && (
              <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12.5 }}
                      onClick={() => setSelectedSurface("whole")}
                      title="Aplicar el próximo estado a la pieza completa">
                Toda la pieza
              </button>
            )}
            <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
              (clic en el número de una pieza también la selecciona completa)
            </span>
          </div>
        )}
        {rmEdit && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                        marginTop: 12, padding: "10px 14px", borderRadius: 10,
                        background: "var(--petrol-soft)", border: "1px solid var(--petrol)" }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              {rmEdit.kind === "recession" ? "Recesión" : "Movilidad"} · pieza {rmEdit.code}:
            </span>
            {[1, 2, 3, 4].map((n) => (
              <button key={n} className="btn btn-ghost"
                      style={{ padding: "6px 14px", fontWeight: 700,
                               ...(rm[rmEdit.code]?.[rmEdit.kind] === n
                                   ? { background: "var(--petrol)", color: "var(--on-brand)" } : {}) }}
                      onClick={() => saveRM(n)}>{n}</button>
            ))}
            <button className="btn btn-ghost" style={{ padding: "6px 12px", fontSize: 13 }}
                    onClick={() => saveRM(null)}>Borrar valor</button>
            <button className="btn btn-ghost" style={{ padding: "6px 10px", fontSize: 13 }}
                    onClick={() => setRmEdit(null)}>Cancelar</button>
          </div>
        )}

        {pendingReg && (
          <div style={{ marginTop: 12, padding: "12px 14px", borderRadius: 10,
                        background: "var(--petrol-soft)", border: "1px solid var(--petrol)",
                        display: "flex", alignItems: "end", gap: 12, flexWrap: "wrap" }}>
            <div style={{ fontSize: 14, fontWeight: 700, paddingBottom: 8 }}>
              Registrar «{pendingReg.label}» · pieza {selected}
            </div>
            <div className="field" style={{ marginBottom: 0, minWidth: 170 }}>
              <label>Superficie</label>
              <select value={selectedSurface} onChange={(e) => setSelectedSurface(e.target.value)}>
                <option value="whole">Toda la pieza</option>
                <option value="vestibular">Vestibular</option>
                <option value="palatal_lingual">Palatina / Lingual</option>
                <option value="mesial">Mesial</option>
                <option value="distal">Distal</option>
                <option value="occlusal">Oclusal / Incisal</option>
              </select>
            </div>
            <div className="field" style={{ marginBottom: 0, flex: "1 1 220px" }}>
              <label>Notas (opcional)</label>
              <input value={toothNotes} onChange={(e) => setToothNotes(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && registerState(pendingReg.stateId)}
                     placeholder="Ej: caries oclusal profunda…" />
            </div>
            <div style={{ display: "flex", gap: 8, paddingBottom: 2 }}>
              <button className="btn btn-primary" onClick={() => registerState(pendingReg.stateId)}>
                Guardar
              </button>
              <button className="btn btn-ghost" onClick={() => { setPendingReg(null); setToothNotes(""); }}>
                Cancelar
              </button>
            </div>
          </div>
        )}

        <OdontogramLegend states={states} onSelect={handleLegendSelect} selectedTooth={selected} />
      </div>

      {selected ? (
        <div>
          <div className="card" style={{ padding: 0 }}>
            <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)", fontWeight: 600 }}>
              Historial de la pieza {selected}
            </div>
            {history.length === 0 ? (
              <div className="empty">Sin registros para esta pieza.</div>
            ) : (
              <table>
                <thead>
                  <tr><th>Fecha</th><th>Estado</th><th>Superficie</th><th>Notas</th><th></th></tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id}>
                      <td className="tabular">{h.date}</td>
                      <td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                          <span style={{ width: 11, height: 11, borderRadius: 3, background: h.state_color, border: "1px solid var(--line)" }} />
                          {h.state_label}
                        </span>
                      </td>
                      <td>{h.surface_display}</td>
                      <td style={{ color: "var(--ink-soft)" }}>{h.notes || "—"}</td>
                      <td style={{ textAlign: "right" }}>
                        <button className="btn btn-ghost"
                                style={{ padding: "4px 10px", fontSize: 12, color: "var(--red)" }}
                                onClick={() => deleteRecord(h)}>
                          Eliminar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      ) : (
        <p style={{ color: "var(--ink-soft)", fontSize: 14 }}>
          Haz clic en una pieza del odontograma para ver su historial o registrar un estado.
        </p>
      )}
    </div>
  );
}

/* ───────────────────────── Evoluciones ───────────────────────── */

const EVOLUTION_TYPES = {
  clinical_note: "Nota clínica",
  prescription: "Receta",
  care_instruction: "Indicación de cuidado",
};

function EvolutionsTab({ patientId }) {
  const [confirm, ConfirmUI] = useConfirm();
  const [editing, setEditing] = useState(null);   // id en edición
  const [editText, setEditText] = useState("");
  const [evolutions, setEvolutions] = useState([]);
  const [form, setForm] = useState({ type: "clinical_note", notes: "", visible_to_patient: false, follow_up_date: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/evolutions/`);
      const data = await resp.json();
      setEvolutions(data.results || data);
    } catch { setError("No se pudieron cargar las evoluciones."); }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const resp = await api(`/patients/${patientId}/evolutions/`, {
        method: "POST",
        body: JSON.stringify({
          ...form,
          follow_up_date: form.follow_up_date || null,
          date: new Date().toISOString().slice(0, 10),
        }),
      });
      if (!resp.ok) {
        let msg = `No se pudo guardar (error ${resp.status}).`;
        try {
          const data = await resp.json();
          msg = data?.error?.message || data?.detail || msg;
        } catch { /* respuesta no-JSON (página de error del servidor) */ }
        throw new Error(msg);
      }
      setForm({ type: "clinical_note", notes: "", visible_to_patient: false, follow_up_date: "" });
      load();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function saveEdit(ev) {
    try {
      const resp = await api(`/evolutions/${ev.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ notes: editText }),
      });
      if (!resp.ok) throw new Error(`No se pudo editar (error ${resp.status}).`);
      setEditing(null);
      load();
    } catch (err) { setError(err.message); }
  }

  async function removeEvolution(ev) {
    const ok = await confirm({
      title: "Eliminar evolución",
      message: `Se eliminará la ${ev.type_display.toLowerCase()} del ${ev.date}.\nEl contenido queda en el registro de auditoría.`,
      confirmLabel: "Eliminar",
      danger: true,
    });
    if (!ok) return;
    try {
      const resp = await api(`/evolutions/${ev.id}/`, { method: "DELETE" });
      if (!resp.ok && resp.status !== 204) throw new Error(`No se pudo eliminar (error ${resp.status}).`);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 18, alignItems: "start" }}>
      {ConfirmUI}
      <form onSubmit={submit} className="card">
        <h3 style={{ marginBottom: 12 }}>Nueva evolución</h3>
        {error && <div className="error-box">{error}</div>}
        <div className="field">
          <label>Tipo</label>
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {Object.entries(EVOLUTION_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Notas *</label>
          <textarea rows={4} required value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="field">
          <label>Fecha de seguimiento (opcional — genera alerta)</label>
          <input type="date" value={form.follow_up_date}
                 onChange={(e) => setForm({ ...form, follow_up_date: e.target.value })} />
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 14 }}>
          <input type="checkbox" checked={form.visible_to_patient}
                 onChange={(e) => setForm({ ...form, visible_to_patient: e.target.checked })} />
          Visible para el paciente en la app
        </label>
        <button className="btn btn-primary" disabled={saving}>
          {saving ? "Guardando…" : "Guardar"}
        </button>
      </form>

      <div>
        {evolutions.length === 0 ? (
          <div className="card"><div className="empty">Sin evoluciones registradas.</div></div>
        ) : (
          <div style={{ position: "relative", paddingLeft: 22 }}>
            {/* Línea vertical de la línea de tiempo */}
            <div style={{ position: "absolute", left: 7, top: 6, bottom: 6, width: 2, background: "var(--line)" }} />
            {evolutions.map((ev) => (
              <div key={ev.id} style={{ position: "relative", marginBottom: 14 }}>
                <div style={{
                  position: "absolute", left: -21, top: 14, width: 12, height: 12,
                  borderRadius: 99, background: ev.type === "prescription" ? "var(--amber)" : "var(--petrol)",
                  border: "2px solid var(--paper)",
                }} />
                <div className="card" style={{ padding: "12px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
                    <div>
                      <span className="tabular" style={{ fontWeight: 700, marginRight: 10 }}>{ev.date}</span>
                      <span className="badge badge-ok">{ev.type_display}</span>
                      {ev.follow_up_date && (
                        <span className="badge badge-warn" style={{ marginLeft: 6 }}>
                          ⏰ Seguimiento: {ev.follow_up_date}
                        </span>
                      )}
                      {ev.visible_to_patient && (
                        <span title="Visible para el paciente" style={{ marginLeft: 6, fontSize: 12 }}>👁</span>
                      )}
                    </div>
                    <div style={{ whiteSpace: "nowrap" }}>
                      {ev.type === "prescription" && editing !== ev.id && (
                        <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                                onClick={async () => {
                                  try {
                                    const r = await api(`/evolutions/${ev.id}/prescription-pdf/`);
                                    if (!r.ok) throw new Error(`Error ${r.status}`);
                                    const blob = await r.blob();
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement("a");
                                    a.href = url; a.download = `receta-${ev.date}.pdf`; a.click();
                                    URL.revokeObjectURL(url);
                                  } catch (err) { setError("No se pudo descargar la receta."); }
                                }}>
                          📄 Receta PDF
                        </button>
                      )}
                      {editing !== ev.id && (
                        <>
                          <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6 }}
                                  onClick={() => { setEditing(ev.id); setEditText(ev.notes); }}>Editar</button>
                          <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, color: "var(--red)", marginLeft: 6 }}
                                  onClick={() => removeEvolution(ev)}>Eliminar</button>
                        </>
                      )}
                    </div>
                  </div>

                  <div style={{ marginTop: 8 }}>
                    {editing === ev.id ? (
                      <div>
                        <textarea rows={3} value={editText}
                                  onChange={(e) => setEditText(e.target.value)}
                                  style={{ width: "100%", padding: 8, border: "1px solid var(--line)", borderRadius: 8 }} />
                        <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
                          <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                                  onClick={() => saveEdit(ev)}>Guardar</button>
                          <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }}
                                  onClick={() => setEditing(null)}>Cancelar</button>
                        </div>
                        <p style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 4 }}>
                          El texto anterior queda en el registro de auditoría.
                        </p>
                      </div>
                    ) : (
                      <p style={{ fontSize: 14, whiteSpace: "pre-line" }}>{ev.notes}</p>
                    )}
                    <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 6 }}>
                      Registrado por: {ev.registered_by || "—"}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
