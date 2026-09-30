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
import { api, readList } from "./api";
import { hoyISO } from "./fechas.mjs";
import { SEXTANTES, calcularIndicadores, decimal } from "./indicadoresBucales.mjs";

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
      const records = await readList(resp);
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
          body: JSON.stringify({ date: hoyISO(), ...payload }),
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

  const r = calcularIndicadores(data.higiene);

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    marginBottom: 14, gap: 10, flexWrap: "wrap" }}>
        <div>
          <h3 style={{ margin: 0 }}>Indicadores de salud bucal</h3>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--ink-soft)" }}>
            Literal I del formulario 033 · {r.completos} de 6 sextantes completos
          </p>
        </div>
        <button className="btn btn-primary" style={{ fontSize: 13 }}
                onClick={save} disabled={saving || !dirty}>
          {saving ? "Guardando…" : dirty ? "Guardar indicadores" : "Guardado"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="success-box">✓ {okMsg}</div>}

      {/* Resultado: lo que el profesional necesita leer de un vistazo. */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                    gap: 10, marginBottom: 16 }}>
        <Resultado titulo="IHO-S" valor={decimal(r.ihos.indice)} escala="de 6" nivel={r.ihos.nivel}
                   ayuda="Índice de higiene oral simplificado: placa + cálculo." destacado />
        <Resultado titulo="Placa (IDB-S)" valor={decimal(r.placa.indice)} escala="de 3" nivel={r.placa.nivel}
                   ayuda={`Suma ${r.placa.suma} en ${r.placa.sextantes} sextantes.`} />
        <Resultado titulo="Cálculo (ICS)" valor={decimal(r.calculo.indice)} escala="de 3" nivel={r.calculo.nivel}
                   ayuda={`Suma ${r.calculo.suma} en ${r.calculo.sextantes} sextantes.`} />
        {/* Sin escala de bueno/malo: el formulario solo pide sí o no por
            sextante, así que se dice cuántos, no un juicio inventado. */}
        <Resultado titulo="Gingivitis"
                   valor={r.gingivitis.sextantes ? String(r.gingivitis.positivos) : "—"}
                   escala={r.gingivitis.sextantes ? `de ${r.gingivitis.sextantes} sextantes` : "sextantes"}
                   nivel={r.gingivitis.sextantes ? (r.gingivitis.positivos ? "regular" : "bueno") : null}
                   texto={r.gingivitis.sextantes ? (r.gingivitis.positivos ? "Presente" : "Sin gingivitis") : null}
                   ayuda="Sextantes con gingivitis sobre los registrados." />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 380px), 1fr))", gap: 20 }}>
        {/* Higiene oral simplificada */}
        <div>
          <div style={secTitle}>Higiene oral simplificada · por sextante</div>
          <div style={{ overflowX: "auto" }}>
            <table className="tabla-ihos" style={{ fontSize: 13, width: "100%" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>Sextante</th>
                  <th title="0 a 3">Placa</th>
                  <th title="0 a 3">Cálculo</th>
                  <th title="0 o 1">Gingivitis</th>
                </tr>
              </thead>
              <tbody>
                {SEXTANTES.map((sx) => (
                  <IndexRow key={sx.clave} sextante={sx} higiene={data.higiene} onChange={setHigiene} />
                ))}
                <tr style={{ background: "var(--petrol-soft)", fontWeight: 700 }}>
                  <td>Totales</td>
                  <td data-etiqueta="Placa" className="tabular" style={{ textAlign: "center" }}>{r.placa.suma}</td>
                  <td data-etiqueta="Cálculo" className="tabular" style={{ textAlign: "center" }}>{r.calculo.suma}</td>
                  <td data-etiqueta="Gingivitis" className="tabular" style={{ textAlign: "center" }}>{r.gingivitis.positivos}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: 11.5, color: "var(--ink-soft)", marginTop: 6 }}>
            Placa y cálculo: 0 ausente · 1 hasta un tercio · 2 hasta dos tercios · 3 más de dos tercios
            de la superficie. Gingivitis: 0 no · 1 sí. Si la pieza índice falta, se usa la siguiente.
          </p>
        </div>

        {/* Enfermedad periodontal, oclusión y fluorosis */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <RadioGroup label="Enfermedad periodontal" value={data.enfermedad_periodontal}
                      onChange={(v) => setField("enfermedad_periodontal", v)}
                      options={[["leve", "Leve", "bueno"], ["moderada", "Moderada", "regular"], ["severa", "Severa", "malo"]]} />
          <RadioGroup label="Tipo de oclusión" value={data.oclusion}
                      onChange={(v) => setField("oclusion", v)}
                      options={[["I", "Angle I"], ["II", "Angle II"], ["III", "Angle III"]]}
                      ayuda={{ I: "Relación molar normal.", II: "Molar inferior distal (distoclusión).",
                               III: "Molar inferior mesial (mesioclusión)." }} />
          <RadioGroup label="Nivel de fluorosis" value={data.fluorosis}
                      onChange={(v) => setField("fluorosis", v)}
                      options={[["leve", "Leve", "bueno"], ["moderada", "Moderada", "regular"], ["severa", "Severa", "malo"]]} />
        </div>
      </div>
    </div>
  );
}

const NIVELES = {
  bueno: { texto: "Bueno", color: "var(--green)", fondo: "var(--green-soft)" },
  regular: { texto: "Regular", color: "var(--amber)", fondo: "var(--amber-soft)" },
  malo: { texto: "Malo", color: "var(--red)", fondo: "var(--red-soft)" },
};

function Resultado({ titulo, valor, escala, nivel, ayuda, destacado, texto }) {
  const n = NIVELES[nivel];
  return (
    <div title={ayuda} style={{ padding: "10px 12px", borderRadius: 10,
                                border: `1px solid ${n ? n.color : "var(--line)"}`,
                                background: n ? n.fondo : "var(--paper)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".03em", color: "var(--ink-soft)",
                    textTransform: "uppercase" }}>{titulo}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 2 }}>
        <span className="tabular" style={{ fontSize: destacado ? 26 : 22, fontWeight: 700,
                                           color: n ? n.color : "var(--ink-faint)" }}>{valor}</span>
        <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>{escala}</span>
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: n ? n.color : "var(--ink-faint)" }}>
        {texto || (n ? n.texto : "Sin datos")}
      </div>
    </div>
  );
}

function IndexRow({ sextante, higiene, onChange }) {
  // Cada sextante usa la primera pieza del triple como clave de registro
  const key = sextante.clave;
  const h = higiene[key] || {};
  const [indice, ...alternas] = sextante.piezas;
  return (
    <tr>
      <td>
        <div style={{ fontWeight: 600 }}>{sextante.nombre}</div>
        <div style={{ fontSize: 11.5, color: "var(--ink-soft)" }}>
          Pieza <strong className="tabular">{indice}</strong>
          <span title="Piezas alternativas si la índice falta"> · alt. {alternas.join(", ")}</span>
        </div>
      </td>
      <td data-etiqueta="Placa"><Puntos value={h.placa} max={3} onChange={(v) => onChange(key, "placa", v)} etiqueta="Placa" /></td>
      <td data-etiqueta="Cálculo"><Puntos value={h.calculo} max={3} onChange={(v) => onChange(key, "calculo", v)} etiqueta="Cálculo" /></td>
      <td data-etiqueta="Gingivitis"><Puntos value={h.gingivitis} max={1} onChange={(v) => onChange(key, "gingivitis", v)} etiqueta="Gingivitis" /></td>
    </tr>
  );
}

// Colores de la puntuación: de nada (verde) a mucho (rojo).
const TONOS = ["var(--green)", "#65a30d", "var(--amber)", "var(--red)"];

/** Puntuación con botones: un toque en vez de abrir un desplegable. Tocar la marcada la borra. */
function Puntos({ value, max, onChange, etiqueta }) {
  return (
    <div role="radiogroup" aria-label={etiqueta}
         style={{ display: "flex", gap: 3, justifyContent: "center" }}>
      {Array.from({ length: max + 1 }, (_, n) => {
        const activo = value === n;
        const tono = max === 1 ? (n === 0 ? TONOS[0] : TONOS[3]) : TONOS[n];
        return (
          <button key={n} type="button" role="radio" aria-checked={activo}
                  onClick={() => onChange(activo ? null : n)}
                  style={{ width: 28, height: 28, borderRadius: 7, fontSize: 13, fontWeight: 700,
                           cursor: "pointer", padding: 0,
                           border: activo ? `2px solid ${tono}` : "1px solid var(--line)",
                           background: activo ? tono : "var(--elev)",
                           color: activo ? "#fff" : "var(--ink-soft)" }}>
            {n}
          </button>
        );
      })}
    </div>
  );
}

function RadioGroup({ label, value, onChange, options, ayuda }) {
  return (
    <div>
      <div style={secTitle}>{label}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {options.map(([k, lbl, nivel]) => {
          const activo = value === k;
          const n = NIVELES[nivel];
          return (
            <button key={k} type="button" onClick={() => onChange(activo ? "" : k)} aria-pressed={activo}
                    style={{ padding: "7px 14px", borderRadius: 8, fontSize: 13, cursor: "pointer",
                             border: activo ? `2px solid ${n ? n.color : "var(--petrol)"}` : "1px solid var(--line)",
                             background: activo ? (n ? n.fondo : "var(--petrol-soft)") : "var(--elev)",
                             color: activo && n ? n.color : "var(--ink)",
                             fontWeight: activo ? 700 : 400 }}>
              {lbl}
            </button>
          );
        })}
      </div>
      {ayuda && value && ayuda[value] && (
        <p style={{ fontSize: 12, color: "var(--ink-soft)", margin: "6px 0 0" }}>{ayuda[value]}</p>
      )}
      {!value && <p style={{ fontSize: 12, color: "var(--ink-faint)", margin: "6px 0 0" }}>Sin registrar.</p>}
    </div>
  );
}

const secTitle = {
  fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em",
  color: "var(--petrol)", marginBottom: 8,
};
