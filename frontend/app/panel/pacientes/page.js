"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "../../../lib/api";

const ORDER_OPTIONS = [
  ["name_asc", "Nombre (A-Z)"],
  ["name_desc", "Nombre (Z-A)"],
  ["created_desc", "Registro (recientes)"],
  ["created_asc", "Registro (antiguos)"],
  ["attention_desc", "Nº de atenciones (mayor)"],
  ["attention_asc", "Nº de atenciones (menor)"],
  ["next_appt_asc", "Próxima cita"],
];

function fmtDateTime(iso) {
  if (!iso) return "—";
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`;
}

export default function PacientesPage() {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("name_asc");
  const [view, setView] = useState("list");   // "list" | "cards"
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (q = "", order = "name_asc") => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("search", q);
      params.set("ordering", order);
      const resp = await api(`/patients/?${params.toString()}`);
      const data = await resp.json();
      setPatients(data.results || data);
    } catch {
      setError("No se pudo cargar la lista de pacientes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(search, ordering); }, [load, ordering]);   // recarga al cambiar orden

  // Recordar la preferencia de vista
  useEffect(() => {
    try {
      const v = localStorage.getItem("patientsView");
      if (v === "cards" || v === "list") setView(v);
    } catch {}
  }, []);

  function setViewPersist(v) {
    setView(v);
    try { localStorage.setItem("patientsView", v); } catch {}
  }

  function handleSearch(e) {
    e.preventDefault();
    load(search, ordering);
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, flexWrap: "wrap", gap: 10 }}>
        <h1 style={{ fontSize: 24 }}>Pacientes</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo paciente"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {showForm && (
        <PatientForm
          onSaved={() => { setShowForm(false); load(search, ordering); }}
        />
      )}

      <form onSubmit={handleSearch} style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <input
          placeholder="Buscar por nombre, apellido o cédula…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: "1 1 240px", padding: "10px 12px", border: "1px solid var(--line)", borderRadius: "var(--radius)" }}
        />
        <button className="btn btn-ghost">Buscar</button>
      </form>

      {/* Barra de controles: ordenar + alternar vista */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "var(--ink-soft)" }}>
          Ordenar por:
          <select value={ordering} onChange={(e) => setOrdering(e.target.value)}
                  style={{ padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 8 }}>
            {ORDER_OPTIONS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </label>

        <div style={{ display: "inline-flex", border: "1px solid var(--line)", borderRadius: 8, overflow: "hidden" }}>
          <button onClick={() => setViewPersist("list")}
                  aria-label="Vista de lista" title="Vista de lista"
                  style={{ padding: "8px 14px", border: "none", cursor: "pointer", fontSize: 14,
                           background: view === "list" ? "var(--petrol)" : "#fff",
                           color: view === "list" ? "#fff" : "var(--ink)" }}>
            ▤ Lista
          </button>
          <button onClick={() => setViewPersist("cards")}
                  aria-label="Vista de tarjetas" title="Vista de tarjetas"
                  style={{ padding: "8px 14px", border: "none", cursor: "pointer", fontSize: 14,
                           background: view === "cards" ? "var(--petrol)" : "#fff",
                           color: view === "cards" ? "#fff" : "var(--ink)" }}>
            ▦ Tarjetas
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card"><div className="empty">Cargando…</div></div>
      ) : patients.length === 0 ? (
        <div className="card"><div className="empty">
          No hay pacientes registrados todavía. Registra el primero con “+ Nuevo paciente”.
        </div></div>
      ) : view === "list" ? (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Cédula</th>
                <th>Teléfono</th>
                <th>Atenciones</th>
                <th>Próxima cita</th>
                <th>Registrado</th>
              </tr>
            </thead>
            <tbody>
              {patients.map((p) => (
                <tr key={p.id} onClick={() => window.location.href = `/panel/paciente/?id=${p.id}`}
                    style={{ cursor: "pointer" }}>
                  <td style={{ fontWeight: 600 }}>{p.full_name}</td>
                  <td className="tabular">{p.national_id}</td>
                  <td className="tabular">{p.phone || "—"}</td>
                  <td className="tabular">{p.attention_count ?? 0}</td>
                  <td className="tabular">{p.next_appointment ? fmtDateTime(p.next_appointment) : "—"}</td>
                  <td className="tabular">{(p.created_at || "").slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ display: "grid", gap: 14,
                      gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))" }}>
          {patients.map((p) => <PatientCard key={p.id} patient={p} />)}
        </div>
      )}
    </div>
  );
}

function PatientCard({ patient: p }) {
  const initials = (p.full_name || "?").split(" ").filter(Boolean).slice(0, 2)
    .map((w) => w[0]).join("").toUpperCase();
  return (
    <div className="card" onClick={() => window.location.href = `/panel/paciente/?id=${p.id}`}
         style={{ cursor: "pointer", display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ width: 46, height: 46, borderRadius: "50%", flexShrink: 0,
                      background: "var(--petrol-soft)", color: "var(--petrol-deep)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontWeight: 700, fontSize: 16 }}>
          {initials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {p.full_name}
          </div>
          <div className="tabular" style={{ fontSize: 13, color: "var(--ink-soft)" }}>{p.national_id}</div>
        </div>
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-soft)", display: "flex", flexDirection: "column", gap: 3 }}>
        <span>📞 {p.phone || "—"}</span>
        <span>🗂 {p.attention_count ?? 0} atencion{(p.attention_count ?? 0) === 1 ? "" : "es"}</span>
        <span>📅 {p.next_appointment ? fmtDateTime(p.next_appointment) : "Sin cita próxima"}</span>
      </div>
    </div>
  );
}

function PatientForm({ onSaved }) {
  const [form, setForm] = useState({
    first_name: "", last_name: "", national_id: "",
    phone: "", email: "", birth_date: "",
  });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const body = { ...form };
      if (!body.birth_date) delete body.birth_date;
      if (!body.email) delete body.email;
      const resp = await api("/patients/", { method: "POST", body: JSON.stringify(body) });
      const data = await resp.json();
      if (!resp.ok) {
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : String(first));
      }
      onSaved();
    } catch (err) {
      setError(err.message || "No se pudo guardar el paciente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginBottom: 14 }}>Nuevo paciente</h3>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        <div className="field">
          <label>Nombres *</label>
          <input required value={form.first_name} onChange={(e) => set("first_name", e.target.value)} />
        </div>
        <div className="field">
          <label>Apellidos *</label>
          <input required value={form.last_name} onChange={(e) => set("last_name", e.target.value)} />
        </div>
        <div className="field">
          <label>Cédula / Identificación *</label>
          <input required value={form.national_id} onChange={(e) => set("national_id", e.target.value)} />
        </div>
        <div className="field">
          <label>Teléfono (WhatsApp)</label>
          <input placeholder="+5939…" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
        </div>
        <div className="field">
          <label>Correo</label>
          <input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} />
        </div>
        <div className="field">
          <label>Fecha de nacimiento</label>
          <input type="date" value={form.birth_date} onChange={(e) => set("birth_date", e.target.value)} />
        </div>
      </div>
      <button className="btn btn-primary" disabled={saving}>
        {saving ? "Guardando…" : "Guardar paciente"}
      </button>
    </form>
  );
}
