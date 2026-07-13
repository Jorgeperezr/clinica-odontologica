"use client";

/**
 * Literal J del formulario MSP 033 — Índices CPO-ceo, calculados
 * automáticamente desde el odontograma, con botón de export del
 * formulario completo a PDF oficial.
 */

import { useCallback, useEffect, useState } from "react";
import { api, apiBase } from "./api";

export default function CpoCeoCard({ patientId, refreshKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/cpo-ceo/`);
      if (resp.ok) setData(await resp.json());
    } catch { /* silencioso */ }
  }, [patientId]);

  useEffect(() => { load(); }, [load, refreshKey]);

  async function exportPdf() {
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/form033/export-pdf/`);
      if (!resp.ok) throw new Error(`No se pudo generar el PDF (error ${resp.status}).`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (err) { setError(err.message); }
  }

  if (!data) return null;
  const { cpo, ceo } = data;

  const cell = { padding: "4px 10px", textAlign: "center", fontVariantNumeric: "tabular-nums" };
  const th = { ...cell, fontSize: 11, color: "var(--ink-soft)", textTransform: "uppercase" };

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>J. Índices CPO-ceo</h3>
        <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={exportPdf}>
          ⬇ Exportar formulario 033 (PDF)
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <table style={{ width: "auto", border: "1px solid var(--line)", borderRadius: 8 }}>
          <thead>
            <tr style={{ background: "var(--petrol-soft)" }}>
              <th style={th}>CPO (permanentes)</th>
              <th style={th}>C</th><th style={th}>P</th><th style={th}>O</th><th style={th}>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ ...cell, fontWeight: 600 }}>Dientes definitivos</td>
              <td style={cell}>{cpo.C}</td><td style={cell}>{cpo.P}</td>
              <td style={cell}>{cpo.O}</td>
              <td style={{ ...cell, fontWeight: 700, background: "#fbe9d9" }}>{cpo.total}</td>
            </tr>
          </tbody>
        </table>

        <table style={{ width: "auto", border: "1px solid var(--line)", borderRadius: 8 }}>
          <thead>
            <tr style={{ background: "var(--petrol-soft)" }}>
              <th style={th}>ceo (temporales)</th>
              <th style={th}>c</th><th style={th}>e</th><th style={th}>o</th><th style={th}>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ ...cell, fontWeight: 600 }}>Dientes deciduos</td>
              <td style={cell}>{ceo.c}</td><td style={cell}>{ceo.e}</td>
              <td style={cell}>{ceo.o}</td>
              <td style={{ ...cell, fontWeight: 700, background: "#fbe9d9" }}>{ceo.total}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 8 }}>
        Calculado automáticamente desde el odontograma ({data.teeth_evaluated} piezas con registro).
        C/c = cariados · P/e = perdidos o con extracción indicada · O/o = obturados o con corona.
      </p>
    </div>
  );
}
