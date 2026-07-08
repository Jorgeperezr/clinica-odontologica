"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "../../../lib/api";

export default function PacientesPage() {
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (q = "") => {
    setLoading(true);
    try {
      const resp = await api(`/patients/${q ? `?search=${encodeURIComponent(q)}` : ""}`);
      const data = await resp.json();
      setPatients(data.results || data);
    } catch {
      setError("No se pudo cargar la lista de pacientes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function handleSearch(e) {
    e.preventDefault();
    load(search);
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24 }}>Pacientes</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nuevo paciente"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {showForm && (
        <PatientForm
          onSaved={() => { setShowForm(false); load(); }}
        />
      )}

      <form onSubmit={handleSearch} style={{ display: "flex", gap: 10, marginBottom: 18 }}>
        <input
          placeholder="Buscar por nombre, apellido o cédula…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, padding: "10px 12px", border: "1px solid var(--line)", borderRadius: "var(--radius)" }}
        />
        <button className="btn btn-ghost">Buscar</button>
      </form>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty">Cargando…</div>
        ) : patients.length === 0 ? (
          <div className="empty">
            No hay pacientes registrados todavía. Registra el primero con “+ Nuevo paciente”.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Cédula</th>
                <th>Teléfono</th>
                <th>Registrado</th>
              </tr>
            </thead>
            <tbody>
              {patients.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600 }}>{p.first_name} {p.last_name}</td>
                  <td className="tabular">{p.national_id}</td>
                  <td className="tabular">{p.phone || "—"}</td>
                  <td className="tabular">{(p.created_at || "").slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
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
