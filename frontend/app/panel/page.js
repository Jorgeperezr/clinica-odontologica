"use client";

import { useEffect, useState } from "react";
import { api, currentUser } from "../../lib/api";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;
const todayISO = () => new Date().toISOString().slice(0, 10);
const fmtTime = (iso) =>
  new Date(iso).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });

const STATUS_BADGE = {
  pending: "badge-warn", confirmed: "badge-ok", completed: "badge-ok",
  cancelled: "badge-danger", no_show: "badge-danger",
};

function firstOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [appointments, setAppointments] = useState(null);
  const [patientCount, setPatientCount] = useState(null);
  const [income, setIncome] = useState(null);
  const [delinquents, setDelinquents] = useState(null);
  const [lowStock, setLowStock] = useState(null);

  useEffect(() => {
    const u = currentUser();
    setUser(u);
    if (!u) return;

    // Cada widget carga según lo que el rol puede ver; los que el
    // backend rechace (403) simplemente no se muestran.
    api(`/agenda/view/?mode=daily&date=${todayISO()}`)
      .then(async (r) => { if (r.ok) { const d = await r.json(); setAppointments(d.results || d); } })
      .catch(() => {});

    api("/patients/?search=")
      .then(async (r) => { if (r.ok) { const d = await r.json(); setPatientCount(d.count ?? (d.results || d).length); } })
      .catch(() => {});

    if (u.role === "admin") {
      api(`/reports/financial/?date_from=${firstOfMonth()}&date_to=${todayISO()}`)
        .then(async (r) => { if (r.ok) setIncome(await r.json()); })
        .catch(() => {});
    }
    if (["admin", "reception"].includes(u.role)) {
      api("/reports/delinquency/")
        .then(async (r) => { if (r.ok) { const d = await r.json(); setDelinquents(d.patients || []); } })
        .catch(() => {});
    }
    if (["admin", "auxiliary"].includes(u.role)) {
      api("/inventory/alerts/low-stock/")
        .then(async (r) => { if (r.ok) { const d = await r.json(); setLowStock(d.low_stock_products || []); } })
        .catch(() => {});
    }
  }, []);

  if (!user) return null;

  const today = new Date().toLocaleDateString("es-EC", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
  const upcoming = (appointments || []).filter((a) =>
    !["cancelled", "completed", "no_show"].includes(a.status));
  const blockingCount = (delinquents || []).filter((p) => p.is_blocking).length;

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 2 }}>Hola, {user.full_name || user.email}</h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 22, textTransform: "capitalize" }}>{today}</p>

      {/* Acciones rápidas */}
      <div style={{ display: "flex", gap: 10, marginBottom: 22, flexWrap: "wrap" }}>
        {["admin", "reception", "doctor"].includes(user.role) && (
          <a className="btn btn-primary" href="/panel/agenda/">+ Nueva cita</a>
        )}
        <a className="btn btn-ghost" href="/panel/pacientes/">+ Nuevo paciente</a>
        {["admin", "reception"].includes(user.role) && (
          <a className="btn btn-ghost" href="/panel/pagos/">Registrar cobro</a>
        )}
      </div>

      {/* Indicadores */}
      <div style={{ display: "flex", gap: 14, marginBottom: 22, flexWrap: "wrap" }}>
        <StatCard label="Citas hoy" value={appointments === null ? "…" : appointments.length}
                  sub={appointments !== null ? `${upcoming.length} activas` : ""} href="/panel/agenda/" />
        <StatCard label="Pacientes" value={patientCount ?? "…"} href="/panel/pacientes/" />
        {income && (
          <StatCard label="Ingresos del mes" value={money(income.total_income)}
                    sub={`${income.payment_count} pagos`} accent href="/panel/reportes/" />
        )}
        {delinquents !== null && (
          <StatCard label="Pacientes morosos" value={delinquents.length}
                    sub={blockingCount ? `${blockingCount} con bloqueo` : ""}
                    danger={delinquents.length > 0} href="/panel/reportes/" />
        )}
        {lowStock !== null && (
          <StatCard label="Stock bajo" value={lowStock.length}
                    danger={lowStock.length > 0} href="/panel/inventario/" />
        )}
      </div>

      {/* Agenda de hoy */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)",
                      display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong>Agenda de hoy</strong>
          <a href="/panel/agenda/" style={{ fontSize: 13 }}>Ver agenda completa →</a>
        </div>
        {appointments === null ? (
          <div className="empty">Cargando…</div>
        ) : appointments.length === 0 ? (
          <div className="empty">No hay citas agendadas para hoy.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Hora</th><th>Paciente</th><th>Doctor</th><th>Estado</th></tr>
            </thead>
            <tbody>
              {appointments.slice(0, 8).map((a) => (
                <tr key={a.id} onClick={() => window.location.href = "/panel/agenda/"}
                    style={{ cursor: "pointer" }}>
                  <td className="tabular" style={{ whiteSpace: "nowrap" }}>
                    {fmtTime(a.scheduled_start)}–{fmtTime(a.scheduled_end)}
                  </td>
                  <td style={{ fontWeight: 600 }}>{a.patient_name}</td>
                  <td>{a.doctor_name}</td>
                  <td><span className={`badge ${STATUS_BADGE[a.status] || "badge-warn"}`}>{a.status_display}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Alertas de stock (si las hay) */}
      {lowStock !== null && lowStock.length > 0 && (
        <div className="card" style={{ padding: 0, marginTop: 18 }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--line)",
                        display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong style={{ color: "var(--red)" }}>⚠ Productos con stock bajo</strong>
            <a href="/panel/inventario/" style={{ fontSize: 13 }}>Ir a inventario →</a>
          </div>
          <table>
            <thead><tr><th>Producto</th><th>Stock actual</th><th>Mínimo</th></tr></thead>
            <tbody>
              {lowStock.slice(0, 5).map((p) => (
                <tr key={p.product_id}>
                  <td style={{ fontWeight: 600 }}>{p.name}</td>
                  <td className="tabular" style={{ color: "var(--red)", fontWeight: 600 }}>{p.current_stock}</td>
                  <td className="tabular">{p.min_stock}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, href, accent, danger }) {
  return (
    <a href={href} className="card"
       style={{
         flex: 1, minWidth: 150, textDecoration: "none", color: "inherit",
         ...(danger ? { borderColor: "var(--red)", background: "var(--red-soft)" } : {}),
       }}>
      <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>
        {label}
      </div>
      <div className="tabular"
           style={{ fontSize: 24, fontWeight: 700,
                    color: danger ? "var(--red)" : accent ? "var(--petrol)" : "var(--ink)" }}>
        {value}
      </div>
      {sub ? <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{sub}</div> : null}
    </a>
  );
}
