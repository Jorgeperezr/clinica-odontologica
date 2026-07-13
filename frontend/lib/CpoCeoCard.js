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

  const base = { border: "1px solid var(--line)", padding: "8px 16px", textAlign: "center",
                 fontVariantNumeric: "tabular-nums" };
  const hdr = { ...base, fontWeight: 700, fontSize: 13, color: "var(--petrol-deep)" };
  const rowLabel = { ...base, fontWeight: 700, background: "var(--mint)", minWidth: 40 };
  const numCell = { ...base, minWidth: 44 };
  const totalCell = { ...base, fontWeight: 700, background: "#f8d9bf" };

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <h3 style={{ margin: 0 }}>J. Índices CPO-ceo</h3>
        <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={exportPdf}>
          ⬇ Exportar formulario 033 (PDF)
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      <div style={{ overflowX: "auto" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "var(--petrol-soft)" }}>
              <th style={hdr}></th>
              <th style={hdr}>C</th><th style={hdr}>P</th><th style={hdr}>O</th>
              <th style={{ ...hdr, minWidth: 120 }}>TOTAL</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={rowLabel}>D</td>
              <td style={numCell}>{cpo.C}</td>
              <td style={numCell}>{cpo.P}</td>
              <td style={numCell}>{cpo.O}</td>
              <td style={totalCell}>{cpo.total}</td>
            </tr>
            <tr style={{ background: "var(--petrol-soft)" }}>
              <th style={hdr}></th>
              <th style={hdr}>c</th><th style={hdr}>e</th><th style={hdr}>o</th>
              <th style={hdr}>TOTAL</th>
            </tr>
            <tr>
              <td style={rowLabel}>d</td>
              <td style={numCell}>{ceo.c}</td>
              <td style={numCell}>{ceo.e}</td>
              <td style={numCell}>{ceo.o}</td>
              <td style={totalCell}>{ceo.total}</td>
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
