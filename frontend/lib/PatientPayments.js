"use client";

/**
 * Cobros del paciente desde su propia ficha (Sprint 45).
 *
 * Evita el salto al módulo de Pagos para el caso más frecuente: cobrar lo
 * del día mientras el paciente está delante. Los abonos a un plan de
 * financiamiento siguen gestionándose en Pagos, que es donde vive esa
 * lógica; aquí se registra el cobro directo.
 *
 * Solo lo ven administración y recepción: no cambia quién puede cobrar.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "./api";

const METHODS = { cash: "Efectivo", transfer: "Transferencia", card: "Tarjeta" };

export default function PatientPayments({ patientId, role }) {
  const [rows, setRows] = useState([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    amount: "", method: "cash", date: new Date().toISOString().slice(0, 10),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const canCharge = ["admin", "reception"].includes(role);

  const load = useCallback(async () => {
    if (!canCharge) return;
    try {
      const resp = await api(`/patients/${patientId}/payments/`);
      if (!resp.ok) return;
      const data = await resp.json();
      setRows(data.results || data);
    } catch { /* sin cobros: la ficha sigue funcionando */ }
  }, [patientId, canCharge]);

  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setError(""); setOkMsg("");
    const amount = Number(form.amount);
    if (!(amount > 0)) { setError("Ingresa un monto mayor que cero."); return; }
    setSaving(true);
    try {
      const resp = await api(`/patients/${patientId}/payments/`, {
        method: "POST", body: JSON.stringify({ ...form, amount: form.amount }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data?.detail || `No se pudo registrar (error ${resp.status}).`);
      setForm({ amount: "", method: "cash", date: new Date().toISOString().slice(0, 10) });
      setAdding(false);
      setOkMsg("Cobro registrado.");
      load();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  if (!canCharge) return null;

  const total = rows.reduce((s, r) => s + Number(r.amount || 0), 0);

  return (
    <div className="card" style={{ marginTop: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10,
                    marginBottom: 12, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}>Cobros</h3>
        {rows.length > 0 && (
          <span className="tabular" style={{ color: "var(--ink-soft)", fontSize: 13 }}>
            {rows.length} · total ${total.toFixed(2)}
          </span>
        )}
        {!adding && (
          <button className="btn btn-primary" style={{ marginLeft: "auto", fontSize: 13 }}
                  onClick={() => { setAdding(true); setOkMsg(""); }}>
            + Registrar cobro
          </button>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="success-box">✓ {okMsg}</div>}

      {adding && (
        <form onSubmit={submit} style={{ display: "grid", gap: 12, marginBottom: 14,
                                         gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                                         alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Monto (USD) *</label>
            <input type="number" step="0.01" min="0.01" required autoFocus
                   value={form.amount}
                   onChange={(e) => setForm({ ...form, amount: e.target.value })}
                   placeholder="0.00" />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Método</label>
            <select value={form.method}
                    onChange={(e) => setForm({ ...form, method: e.target.value })}>
              {Object.entries(METHODS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Fecha</label>
            <input type="date" value={form.date}
                   onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" disabled={saving}>
              {saving ? "Guardando…" : "Guardar"}
            </button>
            <button type="button" className="btn btn-ghost"
                    onClick={() => { setAdding(false); setError(""); }}>
              Cancelar
            </button>
          </div>
        </form>
      )}

      {rows.length === 0 ? (
        <div className="empty">Sin cobros registrados para este paciente.</div>
      ) : (
        <table>
          <thead><tr><th>Fecha</th><th>Método</th><th style={{ textAlign: "right" }}>Monto</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="tabular">{(r.date || "").slice(0, 10)}</td>
                <td>{METHODS[r.method] || r.method}</td>
                <td className="tabular" style={{ textAlign: "right", fontWeight: 600 }}>
                  ${Number(r.amount).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 10 }}>
        Los abonos a un plan de financiamiento se registran en el módulo Pagos.
      </p>
    </div>
  );
}
