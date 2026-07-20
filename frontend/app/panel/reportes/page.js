"use client";

import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;
const METHOD_LABELS = { cash: "Efectivo", transfer: "Transferencia", card: "Tarjeta" };

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function firstOfMonth() { const d = new Date(); return iso(new Date(d.getFullYear(), d.getMonth(), 1)); }
function todayISO() { return iso(new Date()); }

// Rangos rápidos del selector
const QUICK_RANGES = [
  ["Hoy", () => [todayISO(), todayISO()]],
  ["Este mes", () => [firstOfMonth(), todayISO()]],
  ["Mes pasado", () => {
    const d = new Date();
    return [iso(new Date(d.getFullYear(), d.getMonth() - 1, 1)),
            iso(new Date(d.getFullYear(), d.getMonth(), 0))];
  }],
  ["Este año", () => { const d = new Date(); return [`${d.getFullYear()}-01-01`, todayISO()]; }],
];

function fmtPeriod(from, to) {
  const f = (s) => new Date(s + "T12:00:00").toLocaleDateString("es-EC", { day: "numeric", month: "short", year: "numeric" });
  return from === to ? f(from) : `${f(from)} — ${f(to)}`;
}

export default function ReportesPage() {
  const [dateFrom, setDateFrom] = useState(firstOfMonth());
  const [dateTo, setDateTo] = useState(todayISO());
  const [financial, setFinancial] = useState(null);
  const [delinquency, setDelinquency] = useState(null);
  const [production, setProduction] = useState(null);
  const [newPatients, setNewPatients] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadAll(from = dateFrom, to = dateTo) {
    setError(""); setLoading(true);
    try {
      const range = `?date_from=${from}&date_to=${to}`;
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
    finally { setLoading(false); }
  }

  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, []);

  function applyQuick(rangeFn) {
    const [from, to] = rangeFn();
    setDateFrom(from); setDateTo(to);
    loadAll(from, to);
  }

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

  // Totales derivados
  const methodMax = financial ? Math.max(1, ...Object.values(financial.by_method || {}).map(Number)) : 1;
  const prodMax = production?.doctors?.length
    ? Math.max(1, ...production.doctors.map((d) => d.completed_appointments)) : 1;
  const overdueTotal = delinquency?.patients?.reduce((s, p) => s + Number(p.overdue_amount || 0), 0) || 0;

  return (
    <div>
      {/* Reglas de impresión: solo el contenido de reportes, sin menú ni controles */}
      <style>{`
        @media print {
          aside, .no-print { display: none !important; }
          main { padding: 0 !important; }
          .card { box-shadow: none !important; border: 1px solid #ccc !important;
                  break-inside: avoid; }
        }
      `}</style>

      <div className="no-print" style={{ display: "flex", justifyContent: "space-between",
                                          alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ fontSize: 24, margin: 0 }}>Reportes</h1>
        <button className="btn btn-ghost" onClick={() => window.print()}>🖨 Imprimir</button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* Rango de fechas + rangos rápidos */}
      <div className="no-print" style={{ display: "flex", gap: 10, alignItems: "end",
                                          marginBottom: 8, flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Desde</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Hasta</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <button className="btn btn-primary" onClick={() => loadAll()}>Actualizar</button>
      </div>
      <div className="no-print" style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        {QUICK_RANGES.map(([label, fn]) => (
          <button key={label} className="btn btn-ghost" style={{ fontSize: 13, padding: "6px 12px" }}
                  onClick={() => applyQuick(fn)}>{label}</button>
        ))}
      </div>

      {/* Encabezado del período (visible también al imprimir) */}
      <p style={{ fontSize: 14, color: "var(--ink-soft)", marginBottom: 14 }}>
        Período: <strong style={{ color: "var(--ink)" }}>{fmtPeriod(dateFrom, dateTo)}</strong>
      </p>

      {loading ? (
        <div className="card"><div className="empty">Cargando reportes…</div></div>
      ) : (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, alignItems: "start" }}>
        {/* Ingresos con barras por método */}
        <div className="card">
          <h3 style={{ marginBottom: 10 }}>Ingresos del período</h3>
          {financial && (
            <>
              <div className="tabular" style={{ fontSize: 30, fontWeight: 700, color: "var(--petrol)" }}>
                {money(financial.total_income)}
              </div>
              <div style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
                {financial.payment_count} pago{financial.payment_count === 1 ? "" : "s"} registrado{financial.payment_count === 1 ? "" : "s"}
              </div>
              {Object.entries(financial.by_method || {}).map(([m, v]) => (
                <div key={m} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 3 }}>
                    <span>{METHOD_LABELS[m] || m}</span>
                    <span className="tabular" style={{ fontWeight: 600 }}>{money(v)}</span>
                  </div>
                  <div style={{ height: 8, borderRadius: 4, background: "var(--petrol-soft)" }}>
                    <div style={{ height: "100%", borderRadius: 4, background: "var(--petrol)",
                                  width: `${(Number(v) / methodMax) * 100}%`, minWidth: Number(v) > 0 ? 6 : 0 }} />
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Producción por doctor con barras */}
        <div className="card">
          <h3 style={{ marginBottom: 10 }}>Producción por doctor</h3>
          {production?.doctors?.length ? production.doctors.map((d) => (
            <div key={d.doctor_id} style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 3 }}>
                <span>{d.doctor_name}</span>
                <span className="tabular" style={{ fontWeight: 600 }}>
                  {d.completed_appointments} cita{d.completed_appointments === 1 ? "" : "s"}
                </span>
              </div>
              <div style={{ height: 8, borderRadius: 4, background: "var(--petrol-soft)" }}>
                <div style={{ height: "100%", borderRadius: 4, background: "var(--petrol)",
                              width: `${(d.completed_appointments / prodMax) * 100}%`,
                              minWidth: d.completed_appointments > 0 ? 6 : 0 }} />
              </div>
            </div>
          )) : <div style={{ color: "var(--ink-soft)", fontSize: 14 }}>Sin atenciones completadas en el período.</div>}
        </div>

        {/* Morosidad con total y filas accionables */}
        <div className="card" style={{ gridColumn: "1 / -1", padding: 0 }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)",
                        display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
            <span style={{ fontWeight: 600 }}>
              Morosidad {delinquency && <span style={{ fontWeight: 400, color: "var(--ink-soft)", fontSize: 13 }}>
                (umbral: {delinquency.delinquency_threshold_days} días)</span>}
            </span>
            {overdueTotal > 0 && (
              <span className="tabular" style={{ fontWeight: 700, color: "var(--red)" }}>
                Total vencido: {money(overdueTotal)}
              </span>
            )}
          </div>
          {delinquency?.patients?.length ? (
            <table>
              <thead>
                <tr><th>Paciente</th><th>Monto vencido</th><th>Cuotas</th><th>Vencida más antigua</th><th>Días</th><th>Bloquea</th></tr>
              </thead>
              <tbody>
                {delinquency.patients.map((p) => (
                  <tr key={p.patient_id}
                      onClick={() => window.location.href = `/panel/paciente/?id=${p.patient_id}`}
                      style={{ cursor: "pointer",
                               ...(p.is_blocking ? { background: "var(--red-soft)" } : {}) }}>
                    <td style={{ fontWeight: 600 }}>{p.patient_name}</td>
                    <td className="tabular">{money(p.overdue_amount)}</td>
                    <td className="tabular">{p.installment_count}</td>
                    <td className="tabular">{p.oldest_due_date}</td>
                    <td className="tabular" style={p.is_blocking ? { color: "var(--red)", fontWeight: 700 } : {}}>
                      {p.days_overdue}
                    </td>
                    <td>{p.is_blocking
                      ? <span className="badge badge-danger">Sí</span>
                      : <span className="badge badge-warn">Aún no</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="empty">Sin pacientes en mora.</div>}
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
            <div className="no-print" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
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
      )}
    </div>
  );
}
