"use client";

/**
 * Literal N del formulario MSP 033 — Diagnósticos con CIE-10.
 * El profesional busca por código o nombre y marca PRE (presuntivo) o
 * DEF (definitivo). Se integra en la pestaña Odontograma.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

export default function DiagnosisSection({ patientId }) {
  const [diagnoses, setDiagnoses] = useState([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/diagnoses/`);
      const data = await resp.json();
      setDiagnoses(data.results || data);
    } catch { setError("No se pudieron cargar los diagnósticos."); }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>N. Diagnósticos (CIE-10)</h3>
        {!adding && (
          <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={() => setAdding(true)}>
            + Agregar diagnóstico
          </button>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}

      {adding && (
        <DiagnosisForm patientId={patientId}
                       onSaved={() => { setAdding(false); load(); }}
                       onCancel={() => setAdding(false)} />
      )}

      {diagnoses.length === 0 ? (
        <p style={{ color: "var(--ink-soft)", fontSize: 14 }}>Sin diagnósticos registrados.</p>
      ) : (
        <table>
          <thead><tr><th>CIE</th><th>Diagnóstico</th><th>Pieza</th><th>Tipo</th><th>Fecha</th></tr></thead>
          <tbody>
            {diagnoses.map((d) => (
              <tr key={d.id}>
                <td className="tabular" style={{ fontWeight: 600 }}>{d.code || "—"}</td>
                <td>{d.description}</td>
                <td className="tabular">{d.tooth_fdi_code || "—"}</td>
                <td>
                  <span className={`badge ${d.diagnosis_kind === "def" ? "badge-ok" : "badge-warn"}`}>
                    {d.kind_display || (d.diagnosis_kind === "def" ? "Definitivo" : "Presuntivo")}
                  </span>
                </td>
                <td className="tabular">{d.date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function DiagnosisForm({ patientId, onSaved, onCancel }) {
  const [selected, setSelected] = useState(null);   // {code, description}
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [tooth, setTooth] = useState("");
  const [kind, setKind] = useState("pre");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const timer = useRef(null);

  function search(q) {
    setQuery(q);
    setSelected(null);
    clearTimeout(timer.current);
    if (q.length < 2) { setResults([]); return; }
    // Debounce: la búsqueda CIE-10 pega al backend
    timer.current = setTimeout(async () => {
      try {
        const resp = await api(`/cie10/?q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        setResults(data.results || []);
      } catch { /* silencioso */ }
    }, 250);
  }

  async function submit(e) {
    e.preventDefault();
    if (!selected) { setError("Busca y selecciona un código CIE-10."); return; }
    setError(""); setSaving(true);
    try {
      const resp = await api(`/patients/${patientId}/diagnoses/`, {
        method: "POST",
        body: JSON.stringify({
          code: selected.code, description: selected.description,
          tooth_fdi_code: tooth, diagnosis_kind: kind, date,
        }),
      });
      if (!resp.ok) {
        let msg = `No se pudo guardar (error ${resp.status}).`;
        try { const d = await resp.json(); msg = d?.detail || Object.values(d)[0] || msg; } catch {}
        throw new Error(msg);
      }
      onSaved();
    } catch (err) { setError(String(err.message)); }
    finally { setSaving(false); }
  }

  return (
    <form onSubmit={submit} style={{ background: "var(--petrol-soft)", borderRadius: 10, padding: 14, marginBottom: 14 }}>
      {error && <div className="error-box">{error}</div>}

      <div className="field" style={{ position: "relative", marginBottom: 10 }}>
        <label>Buscar diagnóstico (código o nombre CIE-10) *</label>
        <input value={selected ? `${selected.code} — ${selected.description}` : query}
               onChange={(e) => search(e.target.value)}
               placeholder="Ej: K02 o 'caries'…" autoComplete="off" />
        {results.length > 0 && !selected && (
          <div style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 20,
                        background: "#fff", border: "1px solid var(--line)", borderRadius: 8,
                        boxShadow: "0 6px 18px rgba(0,0,0,.12)", maxHeight: 240, overflowY: "auto" }}>
            {results.map((r) => (
              <div key={r.code} onClick={() => { setSelected(r); setResults([]); }}
                   style={{ padding: "8px 12px", cursor: "pointer", fontSize: 14, borderBottom: "1px solid var(--line)" }}>
                <strong className="tabular">{r.code}</strong> — {r.description}
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "90px 1fr 150px", gap: 12, alignItems: "end" }}>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Pieza</label>
          <input value={tooth} onChange={(e) => setTooth(e.target.value)} placeholder="16" />
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Tipo</label>
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="pre">Presuntivo (PRE)</option>
            <option value="def">Definitivo (DEF)</option>
          </select>
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Fecha</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
        <button className="btn btn-primary" disabled={saving || !selected}>
          {saving ? "Guardando…" : "Guardar diagnóstico"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
      </div>
    </form>
  );
}
