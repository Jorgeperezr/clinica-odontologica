"use client";

/**
 * Panel de la Historia Clínica Odontológica MSP (HCU-form.033/2021).
 * Literales B, C, D, E, F, G, I — se integran en la pestaña Odontograma
 * de la ficha del paciente. Los literales A (datos del paciente), H
 * (odontograma), N (diagnósticos), O (profesional, automático) y P
 * (tratamiento) viven en sus propias secciones.
 *
 * Cada historia es "por consulta" (el backend guarda date + snapshot del
 * profesional automáticamente desde la credencial). Se listan las previas
 * y se puede registrar una nueva.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

// D. Antecedentes patológicos PERSONALES (claves oficiales del formulario)
const ANTEC_PERSONALES = [
  "Alergia antibiótico", "Alergia anestesia", "Hemorragias", "VIH / SIDA",
  "Tuberculosis", "Asma", "Diabetes", "Hipertensión arterial",
  "Enf. cardíaca", "Otro",
];

// E. Antecedentes patológicos FAMILIARES
const ANTEC_FAMILIARES = [
  "Cardiopatía", "Hipertensión arterial", "Enf. c. vascular",
  "Endócrino metabólico", "Cáncer", "Tuberculosis", "Enf. mental",
  "Enf. infecciosa", "Mal formación", "Otro",
];

// Examen del sistema estomatognático (13 regiones oficiales)
const REGIONES_ESTOMATO = [
  "Labios", "Mejillas", "Maxilar superior", "Maxilar inferior", "Lengua",
  "Paladar", "Piso de la boca", "Carrillos", "Glándulas salivales",
  "Oro faringe", "A.T.M.", "Ganglios", "Otros",
];

export default function Form033Panel({ patientId }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api(`/patients/${patientId}/form033/`);
      const data = await resp.json();
      setRecords(data.results || data);
    } catch { setError("No se pudo cargar la historia MSP 033."); }
    finally { setLoading(false); }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ marginBottom: 20 }}>
      <details style={{ border: "1px solid var(--line)", borderRadius: "var(--radius)", background: "var(--card)" }}>
        <summary style={{ padding: "14px 18px", cursor: "pointer", fontWeight: 700, fontSize: 15,
                          display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>Historia clínica odontológica</span>
          <span style={{ fontSize: 12, fontWeight: 500, color: "var(--ink-soft)" }}>
            {records.length} registro{records.length === 1 ? "" : "s"}
          </span>
        </summary>

        <div style={{ padding: "0 18px 18px" }}>
          {error && <div className="error-box">{error}</div>}

          {!creating && (
            <button className="btn btn-primary" style={{ marginBottom: 14 }}
                    onClick={() => setCreating(true)}>
              + Registrar consulta
            </button>
          )}

          {creating && (
            <Form033Editor
              patientId={patientId}
              onSaved={() => { setCreating(false); load(); }}
              onCancel={() => setCreating(false)}
            />
          )}

          {loading ? (
            <div className="empty">Cargando…</div>
          ) : records.length === 0 ? (
            <p style={{ color: "var(--ink-soft)", fontSize: 14, padding: "8px 0" }}>
              Sin consultas registradas en el formato MSP 033.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {records.map((r) => <Form033Card key={r.id} record={r} />)}
            </div>
          )}
        </div>
      </details>
    </div>
  );
}

function Form033Card({ record }) {
  const [open, setOpen] = useState(false);
  const personales = Object.entries(record.antecedentes_personales || {})
    .filter(([, v]) => v?.checked).map(([k]) => k);
  const familiares = Object.entries(record.antecedentes_familiares || {})
    .filter(([, v]) => v?.checked).map(([k]) => k);
  const regiones = Object.entries(record.examen_estomatognatico || {})
    .filter(([, v]) => v).map(([k, v]) => `${k}: ${v}`);

  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    cursor: "pointer" }} onClick={() => setOpen(!open)}>
        <div>
          <span className="tabular" style={{ fontWeight: 700 }}>{record.date}</span>
          {record.motivo_consulta && (
            <span style={{ marginLeft: 10, color: "var(--ink-soft)", fontSize: 14 }}>
              {record.motivo_consulta.slice(0, 60)}
            </span>
          )}
        </div>
        <span style={{ fontSize: 13, color: "var(--petrol)" }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 12, fontSize: 14, display: "flex", flexDirection: "column", gap: 8 }}>
          {record.motivo_consulta && <Field label="Motivo de consulta" value={record.motivo_consulta} />}
          {record.embarazada != null && <Field label="Embarazada" value={record.embarazada ? "Sí" : "No"} />}
          {record.enfermedad_actual && <Field label="Enfermedad actual" value={record.enfermedad_actual} />}
          {personales.length > 0 && <Field label="Antecedentes personales" value={personales.join(", ")} />}
          {familiares.length > 0 && <Field label="Antecedentes familiares" value={familiares.join(", ")} />}
          <Field label="Constantes vitales" value={
            [record.temperatura && `T° ${record.temperatura}`, record.pulso && `Pulso ${record.pulso}`,
             record.frecuencia_respiratoria && `FR ${record.frecuencia_respiratoria}`,
             record.presion_arterial && `PA ${record.presion_arterial}`].filter(Boolean).join(" · ") || "—"} />
          {regiones.length > 0 && <Field label="Examen estomatognático" value={regiones.join(" · ")} />}
          {record.registered_by && (
            <div style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 4,
                          borderTop: "1px solid var(--line)", paddingTop: 6 }}>
              Registrado por {record.registered_by}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <span style={{ fontWeight: 600, color: "var(--ink-soft)", fontSize: 12,
                     textTransform: "uppercase", letterSpacing: ".03em" }}>{label}: </span>
      <span>{value}</span>
    </div>
  );
}

function Form033Editor({ patientId, onSaved, onCancel }) {
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    motivo_consulta: "", embarazada: null, enfermedad_actual: "",
    temperatura: "", pulso: "", frecuencia_respiratoria: "", presion_arterial: "",
  });
  const [personales, setPersonales] = useState({});
  const [familiares, setFamiliares] = useState({});
  const [estomato, setEstomato] = useState({});
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  function toggleAntec(setter, key) {
    setter((prev) => ({
      ...prev,
      [key]: { checked: !prev[key]?.checked, detail: prev[key]?.detail || "" },
    }));
  }
  function setAntecDetail(setter, key, detail) {
    setter((prev) => ({ ...prev, [key]: { checked: prev[key]?.checked ?? true, detail } }));
  }

  async function submit(e) {
    e.preventDefault();
    setError(""); setSaving(true);
    try {
      const body = {
        date: form.date,
        motivo_consulta: form.motivo_consulta,
        embarazada: form.embarazada,
        enfermedad_actual: form.enfermedad_actual,
        antecedentes_personales: personales,
        antecedentes_familiares: familiares,
        examen_estomatognatico: estomato,
        temperatura: form.temperatura || null,
        pulso: form.pulso || null,
        frecuencia_respiratoria: form.frecuencia_respiratoria || null,
        presion_arterial: form.presion_arterial,
      };
      const resp = await api(`/patients/${patientId}/form033/`, {
        method: "POST", body: JSON.stringify(body),
      });
      if (!resp.ok) {
        let msg = `No se pudo guardar (error ${resp.status}).`;
        try { const d = await resp.json(); msg = d?.detail || d?.error?.message || msg; } catch {}
        throw new Error(msg);
      }
      onSaved();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  const sectionTitle = {
    fontWeight: 700, fontSize: 13, textTransform: "uppercase", letterSpacing: ".04em",
    color: "var(--petrol)", margin: "18px 0 8px", paddingBottom: 4,
    borderBottom: "2px solid var(--petrol-soft)",
  };

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 16, borderColor: "var(--petrol)" }}>
      {error && <div className="error-box">{error}</div>}

      <div style={{ display: "flex", gap: 14, alignItems: "end", flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Fecha de la consulta *</label>
          <input type="date" required value={form.date} onChange={(e) => set("date", e.target.value)} />
        </div>
      </div>

      {/* Motivo de consulta */}
      <div style={sectionTitle}>Motivo de consulta</div>
      <textarea rows={2} value={form.motivo_consulta}
                onChange={(e) => set("motivo_consulta", e.target.value)}
                style={taStyle} placeholder="Motivo por el que acude el paciente…" />
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, marginTop: 8 }}>
        <span style={{ color: "var(--ink-soft)" }}>Embarazada:</span>
        <select value={form.embarazada === null ? "" : form.embarazada ? "si" : "no"}
                onChange={(e) => set("embarazada", e.target.value === "" ? null : e.target.value === "si")}
                style={{ padding: "6px 10px", border: "1px solid var(--line)", borderRadius: 8 }}>
          <option value="">No aplica</option>
          <option value="si">Sí</option>
          <option value="no">No</option>
        </select>
      </label>

      {/* Enfermedad actual */}
      <div style={sectionTitle}>Enfermedad actual</div>
      <textarea rows={3} value={form.enfermedad_actual}
                onChange={(e) => set("enfermedad_actual", e.target.value)}
                style={taStyle} placeholder="Descripción de la enfermedad actual…" />

      {/* D. Antecedentes personales */}
      <div style={sectionTitle}>Antecedentes patológicos personales</div>
      <AntecGrid options={ANTEC_PERSONALES} state={personales}
                 onToggle={(k) => toggleAntec(setPersonales, k)}
                 onDetail={(k, v) => setAntecDetail(setPersonales, k, v)} />

      {/* E. Antecedentes familiares */}
      <div style={sectionTitle}>Antecedentes patológicos familiares</div>
      <AntecGrid options={ANTEC_FAMILIARES} state={familiares}
                 onToggle={(k) => toggleAntec(setFamiliares, k)}
                 onDetail={(k, v) => setAntecDetail(setFamiliares, k, v)} />

      {/* Constantes vitales */}
      <div style={sectionTitle}>Constantes vitales</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
        <VitalInput label="Temperatura °C" value={form.temperatura} onChange={(v) => set("temperatura", v)} />
        <VitalInput label="Pulso /min" value={form.pulso} onChange={(v) => set("pulso", v)} />
        <VitalInput label="Frec. resp. /min" value={form.frecuencia_respiratoria} onChange={(v) => set("frecuencia_respiratoria", v)} />
        <VitalInput label="Presión art. (mmHg)" value={form.presion_arterial} onChange={(v) => set("presion_arterial", v)} text />
      </div>

      {/* G. Examen estomatognático */}
      <div style={sectionTitle}>Examen del sistema estomatognático</div>
      <p style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: 8 }}>
        Anota los hallazgos en las regiones afectadas. Deja en blanco las que estén normales.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px 14px" }}>
        {REGIONES_ESTOMATO.map((region) => (
          <div key={region} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, minWidth: 130, color: "var(--ink-soft)" }}>{region}</span>
            <input value={estomato[region] || ""}
                   onChange={(e) => setEstomato((p) => ({ ...p, [region]: e.target.value }))}
                   placeholder="Normal"
                   style={{ flex: 1, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 6, fontSize: 13 }} />
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        <button className="btn btn-primary" disabled={saving}>
          {saving ? "Guardando…" : "Guardar consulta"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancelar</button>
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 10 }}>
        Tus datos como profesional se registran automáticamente.
      </p>
    </form>
  );
}

function AntecGrid({ options, state, onToggle, onDetail }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "6px 14px" }}>
      {options.map((opt) => {
        const checked = state[opt]?.checked;
        const isOtro = opt === "Otro";
        return (
          <div key={opt} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14,
                            minWidth: isOtro ? 50 : 0 }}>
              <input type="checkbox" checked={!!checked} onChange={() => onToggle(opt)} />
              {opt}
            </label>
            {(checked && isOtro) && (
              <input value={state[opt]?.detail || ""} onChange={(e) => onDetail(opt, e.target.value)}
                     placeholder="¿Cuál?"
                     style={{ flex: 1, padding: "4px 8px", border: "1px solid var(--line)", borderRadius: 6, fontSize: 13 }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function VitalInput({ label, value, onChange, text }) {
  return (
    <div className="field" style={{ marginBottom: 0 }}>
      <label style={{ fontSize: 12 }}>{label}</label>
      <input type={text ? "text" : "number"} step="0.1" value={value}
             onChange={(e) => onChange(e.target.value)}
             placeholder={text ? "120/80" : ""} />
    </div>
  );
}

const taStyle = {
  width: "100%", padding: "10px 12px", border: "1px solid var(--line)",
  borderRadius: "var(--radius)", fontFamily: "inherit", fontSize: 14, resize: "vertical",
};
