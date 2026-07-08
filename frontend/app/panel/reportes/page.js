"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;
const METHOD_LABELS = { cash: "Efectivo", transfer: "Transferencia", card: "Tarjeta" };

function firstOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}
function todayISO() { return new Date().toISOString().slice(0, 10); }

export default function ReportesPage() {
  const [dateFrom, setDateFrom] = useState(firstOfMonth());
  const [dateTo, setDateTo] = useState(todayISO());
  const [financial, setFinancial] = useState(null);
  const [delinquency, setDelinquency] = useState(null);
  const [production, setProduction] = useState(null);
  const [newPatients, setNewPatients] = useState(null);
  const [error, setError] = useState("");

  async function loadAll() {
    setError("");
    try {
      const range = `?date_from=${dateFrom}&date_to=${dateTo}`;
      const [f, d, p, n] = await Promise.all([
        api(`/reports/financial/${range}`),
        api("/reports/delinquency/"),
        api("/reports/production-by-doctor/"),
        api(`/reports/new-patients/${range}`),
      ]);
      setFinancial(await f.json());
      setDelinquency(await d.json());
      setProduction(await p.json());
      setNewPatients(await n.json());
    } catch { setError("No se pudieron cargar los reportes."); }
  }

  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, []);

  async function downloadExcel(path, filename) {
    try {
      const resp = await api(path);
      if (!resp.ok) throw new Error(`Error ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    } catch { setError("No se pudo descargar el Excel."); }
  }

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Reportes</h1>
      {error && <div className="error-box">{error}</div>}

      {/* Rango de fechas */}
      <div style={{ display: "flex", gap: 10, alignItems: "end", marginBottom: 20, flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Desde</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Hasta</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <button className="btn btn-primary" onClick={loadAll}>Actualizar</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, alignItems: "start" }}>
        {/* Financiero */}
        <div className="card">
          <h3 style={{ marginBottom: 10 }}>Ingresos del período</h3>
          {financial && (
            <>
              <div className="tabular" style={{ fontSize: 30, fontWeight: 700, color: "var(--petrol)" }}>
                {money(financial.total_income)}
              </div>
              <div style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 10 }}>
                {financial.payment_count} pago{financial.payment_count === 1 ? "" : "s"}
              </div>
              {Object.entries(financial.by_method || {}).map(([m, v]) => (
                <div key={m} style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "4px 0" }}>
                  <span>{METHOD_LABELS[m] || m}</span>
                  <span className="tabular" style={{ fontWeight: 600 }}>{money(v)}</span>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Producción por doctor */}
        <div className="card">
          <h3 style={{ marginBottom: 10 }}>Producción por doctor</h3>
          {production?.doctors?.length ? production.doctors.map((d) => (
            <div key={d.doctor_id} style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "5px 0" }}>
              <span>{d.doctor_name}</span>
              <span className="tabular" style={{ fontWeight: 600 }}>
                {d.completed_appointments} cita{d.completed_appointments === 1 ? "" : "s"} completada{d.completed_appointments === 1 ? "" : "s"}
              </span>
            </div>
          )) : <div style={{ color: "var(--ink-soft)", fontSize: 14 }}>Sin datos.</div>}
        </div>

        {/* Morosidad */}
        <div className="card" style={{ gridColumn: "1 / -1", padding: 0 }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)", fontWeight: 600 }}>
            Morosidad {delinquency && <span style={{ fontWeight: 400, color: "var(--ink-soft)", fontSize: 13 }}>
              (umbral: {delinquency.delinquency_threshold_days} días)</span>}
          </div>
          {delinquency?.patients?.length ? (
            <table>
              <thead>
                <tr><th>Paciente</th><th>Monto vencido</th><th>Cuotas</th><th>Vencida más antigua</th><th>Días</th><th>Bloquea</th></tr>
              </thead>
              <tbody>
                {delinquency.patients.map((p) => (
                  <tr key={p.patient_id}>
                    <td style={{ fontWeight: 600 }}>{p.patient_name}</td>
                    <td className="tabular">{money(p.overdue_amount)}</td>
                    <td className="tabular">{p.installment_count}</td>
                    <td className="tabular">{p.oldest_due_date}</td>
                    <td className="tabular">{p.days_overdue}</td>
                    <td>{p.is_blocking
                      ? <span className="badge badge-danger">Sí</span>
                      : <span className="badge badge-warn">Aún no</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="empty">Sin pacientes morosos. 🎉</div>}
        </div>

        {/* Pacientes nuevos + exportaciones */}
        <div className="card" style={{ gridColumn: "1 / -1" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
            <div>
              <h3>Pacientes nuevos en el período</h3>
              <div className="tabular" style={{ fontSize: 26, fontWeight: 700 }}>
                {newPatients ? newPatients.count : "…"}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="btn btn-ghost"
                      onClick={() => downloadExcel(`/reports/new-patients/?date_from=${dateFrom}&date_to=${dateTo}&export=excel`, "pacientes_nuevos.xlsx")}>
                ⬇ Pacientes (Excel)
              </button>
              <button className="btn btn-ghost"
                      onClick={() => downloadExcel("/reports/inventory/?export=excel", "inventario.xlsx")}>
                ⬇ Inventario (Excel)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
