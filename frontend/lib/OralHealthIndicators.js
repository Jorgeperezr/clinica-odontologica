"use client";

/**
 * Literal I del formulario MSP 033 — Indicadores de Salud Bucal.
 * Se integra en la parte superior del odontograma. Reutiliza el registro
 * por consulta del Form033 (campo indicadores_salud_bucal, JSON): se lee
 * del último Form033 del paciente y se guarda creando/actualizando.
 *
 * Estructura oficial:
 *   - Higiene oral simplificada: placa (0-1-2-3), cálculo (0-1-2-3),
 *     gingivitis (0-1) por cada una de las 6 piezas índice.
 *   - Enfermedad periodontal: leve / moderada / severa.
 *   - Tipo de oclusión: Angle I / II / III.
 *   - Nivel de fluorosis: leve / moderada / severa.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

// Las 6 piezas índice del formulario (filas de la tabla de higiene)
const INDEX_TEETH = [
  ["16", "17", "55"],
  ["11", "21", "51"],
  ["26", "27", "65"],
  ["36", "37", "75"],
  ["31", "41", "71"],
  ["46", "47", "85"],
];

const EMPTY = {
  higiene: {},                 // { "16": {placa,calculo,gingivitis}, ... }
  enfermedad_periodontal: "",  // leve|moderada|severa
  oclusion: "",                // I|II|III
  fluorosis: "",               // leve|moderada|severa
};

export default function OralHealthIndicators({ patientId }) {
  const [recordId, setRecordId] = useState(null);   // Form033 más reciente
  const [data, setData] = useState(EMPTY);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/form033/`);
      const list = await resp.json();
      const records = list.results || list;
      if (records.length > 0) {
        setRecordId(records[0].id);
        const ind = records[0].indicadores_salud_bucal || {};
        setData({ ...EMPTY, ...ind, higiene: ind.higiene || {} });
      }
    } catch { /* silencioso: sección opcional */ }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  function setHigiene(tooth, field, value) {
    setData((d) => ({
      ...d,
      higiene: { ...d.higiene, [tooth]: { ...d.higiene[tooth], [field]: value } },
    }));
    setDirty(true);
  }
  function setField(k, v) { setData((d) => ({ ...d, [k]: v })); setDirty(true); }

  async function save() {
    setSaving(true); setError(""); setOkMsg("");
    try {
      const payload = { indicadores_salud_bucal: data };
      let resp;
      if (recordId) {
        resp = await api(`/form033/${recordId}/`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        // No hay Form033 aún: se crea uno con la fecha de hoy
        resp = await api(`/patients/${patientId}/form033/`, {
          method: "POST",
          body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), ...payload }),
        });
      }
      const saved = await resp.json();
      if (!resp.ok) throw new Error(saved?.detail || `Error ${resp.status}`);
      if (saved.id) setRecordId(saved.id);
      setDirty(false);
      setOkMsg("Indicadores guardados.");
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  // Totales de la columna de higiene (suma de placa/cálculo/gingivitis)
  const totals = INDEX_TEETH.flat().reduce((acc, t) => {
    const h = data.higiene[t] || {};
    acc.placa += Number(h.placa || 0);
    acc.calculo += Number(h.calculo || 0);
    acc.gingivitis += Number(h.gingivitis || 0);
    return acc;
  }, { placa: 0, calculo: 0, gingivitis: 0 });

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>I. Indicadores de Salud Bucal</h3>
        <button className="btn btn-primary" style={{ fontSize: 13 }}
                onClick={save} disabled={saving || !dirty}>
          {saving ? "Guardando…" : dirty ? "Guardar indicadores" : "Guardado"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1.4fr) 1fr", gap: 18 }}>
        {/* Higiene oral simplificada */}
        <div>
          <div style={secTitle}>Higiene oral simplificada</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ fontSize: 13 }}>
              <thead>
                <tr>
                  <th colSpan={3} style={{ textAlign: "center" }}>Piezas examinadas</th>
                  <th title="0-1-2-3">Placa</th>
                  <th title="0-1-2-3">Cálculo</th>
                  <th title="0-1">Gingivitis</th>
                </tr>
              </thead>
              <tbody>
                {INDEX_TEETH.map((triple, i) => (
                  <IndexRow key={i} triple={triple} higiene={data.higiene} onChange={setHigiene} />
                ))}
                <tr style={{ background: "var(--petrol-soft)", fontWeight: 700 }}>
                  <td colSpan={3} style={{ textAlign: "center" }}>TOTALES</td>
                  <td className="tabular">{totals.placa}</td>
                  <td className="tabular">{totals.calculo}</td>
                  <td className="tabular">{totals.gingivitis}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 6 }}>
            Placa y cálculo: 0 a 3 · Gingivitis: 0 o 1. Cada fila son las piezas índice de un sextante.
          </p>
        </div>

        {/* Enfermedad periodontal, oclusión y fluorosis */}
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <RadioGroup label="Enfermedad periodontal" value={data.enfermedad_periodontal}
                      onChange={(v) => setField("enfermedad_periodontal", v)}
                      options={[["leve", "Leve"], ["moderada", "Moderada"], ["severa", "Severa"]]} />
          <RadioGroup label="Tipo de oclusión" value={data.oclusion}
                      onChange={(v) => setField("oclusion", v)}
                      options={[["I", "Angle I"], ["II", "Angle II"], ["III", "Angle III"]]} />
          <RadioGroup label="Nivel de fluorosis" value={data.fluorosis}
                      onChange={(v) => setField("fluorosis", v)}
                      options={[["leve", "Leve"], ["moderada", "Moderada"], ["severa", "Severa"]]} />
        </div>
      </div>
    </div>
  );
}

function IndexRow({ triple, higiene, onChange }) {
  // Cada sextante usa la primera pieza del triple como clave de registro
  const key = triple[0];
  const h = higiene[key] || {};
  return (
    <tr>
      {triple.map((t) => <td key={t} className="tabular" style={{ fontWeight: 600 }}>{t}</td>)}
      <td><NumCell value={h.placa} max={3} onChange={(v) => onChange(key, "placa", v)} /></td>
      <td><NumCell value={h.calculo} max={3} onChange={(v) => onChange(key, "calculo", v)} /></td>
      <td><NumCell value={h.gingivitis} max={1} onChange={(v) => onChange(key, "gingivitis", v)} /></td>
    </tr>
  );
}

function NumCell({ value, max, onChange }) {
  return (
    <select value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
            style={{ width: 52, padding: "4px 6px", border: "1px solid var(--line)", borderRadius: 6 }}>
      <option value="">—</option>
      {Array.from({ length: max + 1 }, (_, n) => <option key={n} value={n}>{n}</option>)}
    </select>
  );
}

function RadioGroup({ label, value, onChange, options }) {
  return (
    <div>
      <div style={secTitle}>{label}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {options.map(([k, lbl]) => (
          <button key={k} type="button" onClick={() => onChange(value === k ? "" : k)}
                  style={{ padding: "7px 12px", borderRadius: 8, fontSize: 13, cursor: "pointer",
                           border: value === k ? "2px solid var(--petrol)" : "1px solid var(--line)",
                           background: value === k ? "var(--petrol-soft)" : "#fff",
                           fontWeight: value === k ? 600 : 400 }}>
            {lbl}
          </button>
        ))}
      </div>
    </div>
  );
}

const secTitle = {
  fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em",
  color: "var(--petrol)", marginBottom: 8,
};
