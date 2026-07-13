"use client";

/**
 * Literales L (pedido de exámenes complementarios) y M (informe de
 * exámenes) del formulario MSP 033. Se integra en la pestaña Documentos.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

const CATEGORIES = {
  biometria: "Biometría", quimica_sanguinea: "Química sanguínea",
  rayos_x: "Rayos X", otros: "Otros",
};

export default function ExamRequestsSection({ patientId }) {
  const [exams, setExams] = useState([]);
  const [adding, setAdding] = useState(false);
  const [reportingId, setReportingId] = useState(null);
  const [reportText, setReportText] = useState("");
  const [form, setForm] = useState({ category: "biometria", detail: "" });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/exam-requests/`);
      const data = await resp.json();
      setExams(data.results || data);
    } catch { setError("No se pudieron cargar los exámenes."); }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  async function createExam(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/exam-requests/`, {
        method: "POST", body: JSON.stringify(form),
      });
      if (!resp.ok) throw new Error(`No se pudo crear el pedido (error ${resp.status}).`);
      setForm({ category: "biometria", detail: "" });
      setAdding(false);
      load();
    } catch (err) { setError(err.message); }
  }

  async function saveReport(exam) {
    setError("");
    try {
      const resp = await api(`/exam-requests/${exam.id}/report/`, {
        method: "PATCH", body: JSON.stringify({ report_notes: reportText }),
      });
      if (!resp.ok) throw new Error(`No se pudo guardar el informe (error ${resp.status}).`);
      setReportingId(null); setReportText("");
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>L / M. Exámenes complementarios</h3>
        {!adding && (
          <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={() => setAdding(true)}>
            + Pedir examen
          </button>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}

      {adding && (
        <form onSubmit={createExam} style={{ background: "var(--petrol-soft)", borderRadius: 10, padding: 14, marginBottom: 14 }}>
          <div style={{ display: "grid", gridTemplateColumns: "180px 1fr auto", gap: 12, alignItems: "end" }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Tipo (L)</label>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                {Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Examen solicitado</label>
              <input required value={form.detail}
                     onChange={(e) => setForm({ ...form, detail: e.target.value })}
                     placeholder="Ej: Biometría hemática completa" />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary">Pedir</button>
              <button type="button" className="btn btn-ghost" onClick={() => setAdding(false)}>✕</button>
            </div>
          </div>
        </form>
      )}

      {exams.length === 0 ? (
        <p style={{ color: "var(--ink-soft)", fontSize: 14 }}>Sin pedidos de exámenes.</p>
      ) : (
        <table>
          <thead><tr><th>Tipo</th><th>Solicitado (L)</th><th>Estado</th><th>Informe (M)</th><th></th></tr></thead>
          <tbody>
            {exams.map((ex) => (
              <tr key={ex.id}>
                <td>{ex.category_display}</td>
                <td>{ex.detail}</td>
                <td>
                  <span className={`badge ${ex.status === "reported" ? "badge-ok" : "badge-warn"}`}>
                    {ex.status_display}
                  </span>
                </td>
                <td style={{ maxWidth: 260 }}>
                  {reportingId === ex.id ? (
                    <div>
                      <textarea rows={2} value={reportText} onChange={(e) => setReportText(e.target.value)}
                                style={{ width: "100%", padding: 6, border: "1px solid var(--line)", borderRadius: 6 }} />
                      <div style={{ marginTop: 4, display: "flex", gap: 6 }}>
                        <button className="btn btn-primary" style={{ padding: "3px 10px", fontSize: 12 }}
                                onClick={() => saveReport(ex)}>Guardar</button>
                        <button className="btn btn-ghost" style={{ padding: "3px 10px", fontSize: 12 }}
                                onClick={() => setReportingId(null)}>Cancelar</button>
                      </div>
                    </div>
                  ) : (ex.report_notes || <span style={{ color: "var(--ink-soft)" }}>—</span>)}
                </td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {reportingId !== ex.id && (
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => { setReportingId(ex.id); setReportText(ex.report_notes || ""); }}>
                      {ex.report_notes ? "Editar informe" : "Cargar informe"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
