"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import BackButton from "../../../lib/BackButton";
import { useConfirm } from "../../../lib/ConfirmDialog";

const METHODS = { cash: "Efectivo", transfer: "Transferencia", card: "Tarjeta" };
const money = (v) => `$${Number(v || 0).toFixed(2)}`;

export default function PagosPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [patient, setPatient] = useState(null);

  async function search(q) {
    setQuery(q);
    setPatient(null);
    if (q.length < 2) { setResults([]); return; }
    try {
      const resp = await api(`/patients/?search=${encodeURIComponent(q)}`);
      const data = await resp.json();
      setResults((data.results || data).slice(0, 6));
    } catch { /* silencioso */ }
  }

  return (
    <div>
      <BackButton fallback="/panel/" />
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Pagos</h1>

      <div className="field" style={{ position: "relative", maxWidth: 460 }}>
        <label>Paciente</label>
        <input
          placeholder="Buscar por nombre o cédula…"
          value={patient ? `${patient.full_name} (${patient.national_id})` : query}
          onChange={(e) => search(e.target.value)}
        />
        {results.length > 0 && !patient && (
          <div style={{
            position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
            background: "var(--elev)", border: "1px solid var(--line)", borderRadius: 8,
            boxShadow: "0 6px 18px rgba(0,0,0,.08)",
          }}>
            {results.map((p) => (
              <div key={p.id} onClick={() => { setPatient(p); setResults([]); }}
                   style={{ padding: "9px 12px", cursor: "pointer", fontSize: 14 }}>
                <strong>{p.full_name}</strong> · <span className="tabular">{p.national_id}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {patient ? (
        <PatientBilling patient={patient} />
      ) : (
        <p style={{ color: "var(--ink-soft)", fontSize: 14 }}>
          Busca un paciente para ver su estado de cuenta, presupuestos y cuotas.
        </p>
      )}
    </div>
  );
}

/* ───────────── Cuenta del paciente ───────────── */

function PatientBilling({ patient }) {
  const [confirm, ConfirmUI] = useConfirm();
  const [statement, setStatement] = useState(null);
  const [budgets, setBudgets] = useState([]);
  const [treatments, setTreatments] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [stResp, buResp] = await Promise.all([
        api(`/patients/${patient.id}/account-statement/`),
        api(`/patients/${patient.id}/budgets/`),
      ]);
      setStatement(await stResp.json());
      const bu = await buResp.json();
      setBudgets(bu.results || bu);
    } catch { setError("No se pudo cargar la información de pagos."); }
  }, [patient.id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api("/config/treatments/?is_active=true").then(async (r) => {
      const data = await r.json();
      setTreatments(data.results || data);
    }).catch(() => {});
  }, []);

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}

      {statement && <StatementCards statement={statement} />}

      <BudgetsSection
        patient={patient} budgets={budgets} treatments={treatments}
        confirm={confirm} onChange={load}
      />
    </div>
  );
}

function StatementCards({ statement }) {
  const isDelinquent = statement.overdue_count > 0;
  const card = { flex: 1, minWidth: 150 };
  return (
    <div style={{ display: "flex", gap: 14, margin: "6px 0 22px", flexWrap: "wrap" }}>
      <div className="card" style={card}>
        <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>Total</div>
        <div className="tabular" style={{ fontSize: 22, fontWeight: 700 }}>{money(statement.total_amount)}</div>
      </div>
      <div className="card" style={card}>
        <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>Pagado</div>
        <div className="tabular" style={{ fontSize: 22, fontWeight: 700, color: "var(--petrol)" }}>{money(statement.total_paid)}</div>
      </div>
      <div className="card" style={card}>
        <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>Saldo</div>
        <div className="tabular" style={{ fontSize: 22, fontWeight: 700 }}>{money(statement.balance)}</div>
      </div>
      <div className="card" style={{ ...card, ...(isDelinquent ? { borderColor: "var(--red)", background: "var(--red-soft)" } : {}) }}>
        <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>Cuotas vencidas</div>
        <div className="tabular" style={{ fontSize: 22, fontWeight: 700, color: isDelinquent ? "var(--red)" : "var(--ink)" }}>
          {statement.overdue_count} · {money(statement.overdue_amount)}
        </div>
      </div>
    </div>
  );
}

/* ───────────── Presupuestos ───────────── */

const BUDGET_BADGE = { draft: "badge-warn", approved: "badge-ok", rejected: "badge-danger" };

function BudgetsSection({ patient, budgets, treatments, confirm, onChange }) {
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  async function createBudget() {
    setError("");
    try {
      const resp = await api(`/patients/${patient.id}/budgets/`, {
        method: "POST",
        body: JSON.stringify({ patient: patient.id, notes: "" }),
      });
      if (!resp.ok) throw new Error(`No se pudo crear el presupuesto (error ${resp.status}).`);
      onChange();
    } catch (err) { setError(err.message); }
    finally { setCreating(false); }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h2 style={{ fontSize: 18 }}>Presupuestos</h2>
        <button className="btn btn-primary" disabled={creating}
                onClick={() => { setCreating(true); createBudget(); }}>
          + Nuevo presupuesto
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}

      {budgets.length === 0 ? (
        <div className="card"><div className="empty">Sin presupuestos. Crea el primero.</div></div>
      ) : (
        budgets.map((b) => (
          <BudgetCard key={b.id} budget={b} treatments={treatments}
                      confirm={confirm} onChange={onChange} />
        ))
      )}
    </div>
  );
}

function BudgetCard({ budget, treatments, confirm, onChange }) {
  const [item, setItem] = useState({ treatment: "", tooth_fdi_code: "", quantity: 1, unit_price: "" });
  const [plan, setPlan] = useState({ installment_count: 3, first_due_date: new Date().toISOString().slice(0, 10) });
  const [installments, setInstallments] = useState(null);
  const [paying, setPaying] = useState(null); // {id, amount, method}
  const [error, setError] = useState("");

  const hasPlan = installments && installments.length > 0;

  const loadInstallments = useCallback(async () => {
    // El plan cuelga del presupuesto: buscamos sus cuotas si existe
    try {
      const resp = await api(`/patients/${budget.patient}/account-statement/`);
      if (resp.ok) { /* statement ya lo maneja el padre */ }
    } catch { /* noop */ }
  }, [budget.patient]);

  function selectTreatment(id) {
    const t = treatments.find((x) => x.id === id);
    setItem({ ...item, treatment: id, unit_price: t ? t.base_price : "" });
  }

  async function addItem() {
    setError("");
    try {
      const resp = await api(`/budgets/${budget.id}/items/`, {
        method: "POST",
        body: JSON.stringify(item),
      });
      if (!resp.ok) throw new Error(`No se pudo agregar el ítem (error ${resp.status}).`);
      setItem({ treatment: "", tooth_fdi_code: "", quantity: 1, unit_price: "" });
      onChange();
    } catch (err) { setError(err.message); }
  }

  async function approve() {
    const ok = await confirm({
      title: "Aprobar presupuesto",
      message: `Total: ${money(budget.total_amount)}.\\nUna vez aprobado se puede generar el plan de cuotas.`,
      confirmLabel: "Aprobar",
    });
    if (!ok) return;
    try {
      const resp = await api(`/budgets/${budget.id}/approve/`, { method: "POST" });
      if (!resp.ok) throw new Error(`No se pudo aprobar (error ${resp.status}).`);
      onChange();
    } catch (err) { setError(err.message); }
  }

  async function generatePlan() {
    const ok = await confirm({
      title: "Generar plan de pago",
      message: `${plan.installment_count} cuotas mensuales desde ${plan.first_due_date}.\\nTotal: ${money(budget.total_amount)}.`,
      confirmLabel: "Generar",
    });
    if (!ok) return;
    setError("");
    try {
      const resp = await api(`/budgets/${budget.id}/generate-payment-plan/`, {
        method: "POST",
        body: JSON.stringify(plan),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data?.detail || data?.error?.message || `Error ${resp.status}.`);
      }
      setInstallments(data.installments || []);
      onChange();
    } catch (err) { setError(err.message); }
  }

  async function submitPayment() {
    setError("");
    try {
      const resp = await api(`/installments/${paying.id}/pay/`, {
        method: "POST",
        body: JSON.stringify({ amount: paying.amount, method: paying.method }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        const detail = data?.error?.details || data?.error?.message || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : String(first));
      }
      setInstallments((list) => list.map((i) => (i.id === paying.id ? data : i)));
      setPaying(null);
      onChange();
    } catch (err) { setError(err.message); }
  }

  async function viewInstallments() {
    // El plan se identifica vía el presupuesto: pedimos las cuotas del plan.
    // El backend expone /payment-plans/{plan_id}/installments/, y el plan
    // es OneToOne con el budget — usamos el endpoint de estado por paciente
    // como fallback simple: pedir cuotas directamente por el plan del budget.
    setError("");
    try {
      const resp = await api(`/budgets/${budget.id}/`);
      const data = await resp.json();
      const planId = data.payment_plan_id;
      if (!planId) { setError("Este presupuesto aún no tiene plan de pago."); return; }
      const iResp = await api(`/payment-plans/${planId}/installments/`);
      const iData = await iResp.json();
      setInstallments(iData.results || iData);
    } catch { setError("No se pudieron cargar las cuotas."); }
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div>
          <span className={`badge ${BUDGET_BADGE[budget.status] || "badge-warn"}`}>{budget.status_display}</span>
          <span className="tabular" style={{ marginLeft: 12, fontWeight: 700, fontSize: 17 }}>
            {money(budget.total_amount)}
          </span>
          <span style={{ marginLeft: 10, fontSize: 12, color: "var(--ink-soft)" }}>
            {(budget.created_at || "").slice(0, 10)}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {budget.status === "draft" && budget.items?.length > 0 && (
            <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={approve}>Aprobar</button>
          )}
          {budget.status === "approved" && (
            <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={viewInstallments}>Ver cuotas</button>
          )}
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {/* Ítems */}
      {budget.items?.length > 0 && (
        <table style={{ marginBottom: 12 }}>
          <thead><tr><th>Tratamiento</th><th>Pieza</th><th>Cant.</th><th>P. unitario</th><th>Subtotal</th></tr></thead>
          <tbody>
            {budget.items.map((it) => (
              <tr key={it.id}>
                <td>{it.treatment_name}</td>
                <td className="tabular">{it.tooth_fdi_code || "—"}</td>
                <td className="tabular">{it.quantity}</td>
                <td className="tabular">{money(it.unit_price)}</td>
                <td className="tabular" style={{ fontWeight: 600 }}>{money(it.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Agregar ítem (solo en borrador) */}
      {budget.status === "draft" && (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 80px 70px 110px auto", gap: 8, alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Tratamiento</label>
            <select value={item.treatment} onChange={(e) => selectTreatment(e.target.value)}>
              <option value="">Seleccionar…</option>
              {treatments.map((t) => (
                <option key={t.id} value={t.id}>{t.name} — {money(t.base_price)}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Pieza</label>
            <input value={item.tooth_fdi_code} placeholder="16"
                   onChange={(e) => setItem({ ...item, tooth_fdi_code: e.target.value })} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Cant.</label>
            <input type="number" min={1} value={item.quantity}
                   onChange={(e) => setItem({ ...item, quantity: Number(e.target.value) })} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Precio</label>
            <input type="number" step="0.01" value={item.unit_price}
                   onChange={(e) => setItem({ ...item, unit_price: e.target.value })} />
          </div>
          <button className="btn btn-ghost" disabled={!item.treatment || !item.unit_price} onClick={addItem}>
            + Agregar
          </button>
        </div>
      )}

      {/* Generar plan (aprobado, sin plan aún) */}
      {budget.status === "approved" && !hasPlan && (
        <div style={{ display: "flex", gap: 10, alignItems: "end", marginTop: 10, flexWrap: "wrap" }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Nº de cuotas</label>
            <input type="number" min={1} max={60} value={plan.installment_count}
                   onChange={(e) => setPlan({ ...plan, installment_count: Number(e.target.value) })}
                   style={{ width: 100 }} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Primera fecha de pago</label>
            <input type="date" value={plan.first_due_date}
                   onChange={(e) => setPlan({ ...plan, first_due_date: e.target.value })} />
          </div>
          <button className="btn btn-primary" onClick={generatePlan}>Generar plan de cuotas</button>
        </div>
      )}

      {/* Cuotas */}
      {hasPlan && (
        <div style={{ marginTop: 12 }}>
          <h4 style={{ marginBottom: 8, fontSize: 14 }}>Cuotas</h4>
          <table>
            <thead><tr><th>#</th><th>Vence</th><th>Monto</th><th>Pagado</th><th>Saldo</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {installments.map((i) => {
                const badge = i.status === "paid" ? "badge-ok" : i.status === "overdue" ? "badge-danger" : "badge-warn";
                return (
                  <tr key={i.id}>
                    <td className="tabular">{i.number}</td>
                    <td className="tabular">{i.due_date}</td>
                    <td className="tabular">{money(i.amount)}</td>
                    <td className="tabular">{money(i.total_paid)}</td>
                    <td className="tabular" style={{ fontWeight: 600 }}>{money(i.balance)}</td>
                    <td><span className={`badge ${badge}`}>{i.status_display}</span></td>
                    <td style={{ textAlign: "right" }}>
                      {i.status !== "paid" && (
                        <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                                onClick={() => setPaying({ id: i.id, number: i.number, amount: i.balance, method: "cash" })}>
                          Cobrar
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {paying && (
            <div style={{ display: "flex", gap: 10, alignItems: "end", marginTop: 12,
                          padding: 14, background: "var(--petrol-soft)", borderRadius: 10, flexWrap: "wrap" }}>
              <strong style={{ alignSelf: "center" }}>Cobrar cuota {paying.number}:</strong>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Monto</label>
                <input type="number" step="0.01" min="0.01" value={paying.amount}
                       onChange={(e) => setPaying({ ...paying, amount: e.target.value })}
                       style={{ width: 120 }} />
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Método</label>
                <select value={paying.method}
                        onChange={(e) => setPaying({ ...paying, method: e.target.value })}>
                  {Object.entries(METHODS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <button className="btn btn-primary" onClick={submitPayment}>Confirmar cobro</button>
              <button className="btn btn-ghost" onClick={() => setPaying(null)}>Cancelar</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
