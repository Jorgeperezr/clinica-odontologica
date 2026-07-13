"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "../../../lib/api";
import Odontogram from "../../../lib/Odontogram";
import Form033Panel from "../../../lib/Form033Panel";
import DiagnosisSection from "../../../lib/DiagnosisTab";
import CpoCeoCard from "../../../lib/CpoCeoCard";
import ExamRequestsSection from "../../../lib/ExamRequestsSection";
import { useConfirm } from "../../../lib/ConfirmDialog";
import { ConsentsTab, DocumentsTab, PlanTab } from "../../../lib/ClinicalTabs";

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
  const [tab, setTab] = useState("odontograma");

  useEffect(() => {
    api(`/patients/${id}/`).then(async (r) => setPatient(await r.json())).catch(() => {});
  }, [id]);

  if (!patient) return <div className="empty">Cargando…</div>;

  return (
    <div>
      <a href="/panel/pacientes/" style={{ fontSize: 13 }}>← Pacientes</a>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", margin: "8px 0 4px" }}>
        <h1 style={{ fontSize: 24 }}>{patient.full_name}</h1>
        <span className="tabular" style={{ color: "var(--ink-soft)", fontSize: 14 }}>
          CI {patient.national_id} {patient.phone ? `· ${patient.phone}` : ""}
        </span>
      </div>

      <div style={{ display: "flex", gap: 4, margin: "16px 0 20px", borderBottom: "1px solid var(--line)" }}>
        {[["odontograma", "Odontograma"], ["evoluciones", "Evoluciones"],
          ["plan", "Plan de tratamiento"], ["documentos", "Documentos"],
          ["consentimientos", "Consentimientos"]].map(([key, label]) => (
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
    </div>
  );
}

/* ───────────────────────── Odontograma ───────────────────────── */

function OdontogramTab({ patientId }) {
  const [confirm, ConfirmUI] = useConfirm();
  const [toothNotes, setToothNotes] = useState("");
  const [states, setStates] = useState([]);       // catálogo de estados
  const [teeth, setTeeth] = useState({});          // { "16": {color,label,...} }
  const [selected, setSelected] = useState(null);  // pieza seleccionada
  const [history, setHistory] = useState([]);      // historial de la pieza
  const [error, setError] = useState("");

  const loadCurrent = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/odontogram/current/`);
      const data = await resp.json();
      const map = {};
      // Nos quedamos con el estado de "toda la pieza" o el más reciente por pieza
      for (const t of data.teeth || []) {
        if (!map[t.tooth_fdi_code]) {
          map[t.tooth_fdi_code] = { color: t.state_color, label: t.state_label };
        }
      }
      setTeeth(map);
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

  function handleToothClick(code) {
    setSelected(code);
    loadHistory(code);
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

  async function registerState(stateId) {
    const stateLabel = states.find((s) => s.id === stateId)?.label || "este estado";
    const ok = await confirm({
      title: `Registrar estado en la pieza ${selected}`,
      message: `Se añadirá "${stateLabel}" al historial de la pieza.\nEl historial no se sobrescribe.`,
      confirmLabel: "Registrar",
    });
    if (!ok) return;
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/tooth-records/`, {
        method: "POST",
        body: JSON.stringify({
          tooth_fdi_code: selected,
          surface: "whole",
          state: stateId,
          notes: toothNotes,
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
      await loadHistory(selected);
      setToothNotes("");
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      <Form033Panel patientId={patientId} />
      <CpoCeoCard patientId={patientId} refreshKey={Object.keys(teeth).length} />
      <DiagnosisSection patientId={patientId} />
      {error && <div className="error-box">{error}</div>}

      <div className="card" style={{ marginBottom: 18 }}>
        <Odontogram teethState={teeth} selectedTooth={selected} onToothClick={handleToothClick} />

        {/* Leyenda del catálogo */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 16px", marginTop: 16, fontSize: 12, color: "var(--ink-soft)" }}>
          {states.map((s) => (
            <span key={s.id} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 12, height: 12, borderRadius: 3, background: s.color, border: "1px solid var(--line)", display: "inline-block" }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {selected ? (
        <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 18, alignItems: "start" }}>
          <div className="card">
            <h3 style={{ marginBottom: 4 }}>Pieza {selected}</h3>
            <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 10 }}>
              Registrar nuevo estado (no borra el historial):
            </p>
            <div className="field" style={{ marginBottom: 10 }}>
              <label>Notas (opcional, se guardan con el estado)</label>
              <textarea rows={2} value={toothNotes}
                        onChange={(e) => setToothNotes(e.target.value)}
                        placeholder="Ej: caries oclusal profunda…" />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {states.map((s) => (
                <button key={s.id} className="btn btn-ghost"
                        style={{ justifyContent: "flex-start", gap: 10 }}
                        onClick={() => registerState(s.id)}>
                  <span style={{ width: 14, height: 14, borderRadius: 4, background: s.color, border: "1px solid var(--line)" }} />
                  {s.label}
                </button>
              ))}
            </div>
          </div>

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
