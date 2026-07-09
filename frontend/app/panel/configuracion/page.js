"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;

const PARAM_LABELS = {
  dias_morosidad: "Días para considerar moroso a un paciente",
  ventana_recordatorio_horas: "Horas de anticipación del recordatorio de cita",
  stock_minimo_default: "Stock mínimo por defecto para productos nuevos",
  dias_alerta_vencimiento: "Días de anticipación de la alerta de vencimiento",
};

export default function ConfiguracionPage() {
  const [tab, setTab] = useState("tratamientos");

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Configuración</h1>

      <div style={{ display: "flex", gap: 4, marginBottom: 20, borderBottom: "1px solid var(--line)" }}>
        {[["tratamientos", "Tratamientos"], ["especialidades", "Especialidades"], ["usuarios", "Usuarios"], ["parametros", "Parámetros"]].map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            style={{
              padding: "9px 16px", border: "none", background: "transparent",
              fontWeight: 600, fontSize: 14,
              color: tab === k ? "var(--petrol)" : "var(--ink-soft)",
              borderBottom: tab === k ? "3px solid var(--petrol)" : "3px solid transparent",
            }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "tratamientos" && <TreatmentsTab />}
      {tab === "especialidades" && <SpecialtiesTab />}
      {tab === "usuarios" && <UsersTab />}
      {tab === "parametros" && <ParametersTab />}
    </div>
  );
}

/* ── Tratamientos ── */
function TreatmentsTab() {
  const [treatments, setTreatments] = useState([]);
  const [specialties, setSpecialties] = useState([]);
  const [form, setForm] = useState({ name: "", specialty: "", base_price: "" });
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [tResp, sResp] = await Promise.all([
        api("/config/treatments/"), api("/specialties/"),
      ]);
      const t = await tResp.json(); setTreatments(t.results || t);
      const s = await sResp.json(); setSpecialties(s.results || s);
    } catch { setError("No se pudo cargar el catálogo."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api("/config/treatments/", { method: "POST", body: JSON.stringify(form) });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : `Error ${resp.status}`);
      }
      setForm({ name: "", specialty: "", base_price: "" });
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      <form onSubmit={submit} className="card" style={{ marginBottom: 18 }}>
        <h3 style={{ marginBottom: 12 }}>Nuevo tratamiento</h3>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1.5fr 1fr auto", gap: "0 12px", alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Nombre *</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Especialidad *</label>
            <select required value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })}>
              <option value="">Seleccionar…</option>
              {specialties.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Precio base *</label>
            <input type="number" step="0.01" required value={form.base_price}
                   onChange={(e) => setForm({ ...form, base_price: e.target.value })} /></div>
          <button className="btn btn-primary">Guardar</button>
        </div>
      </form>

      <div className="card" style={{ padding: 0 }}>
        {treatments.length === 0 ? <div className="empty">Sin tratamientos en el catálogo.</div> : (
          <table>
            <thead><tr><th>Tratamiento</th><th>Especialidad</th><th>Precio base</th><th>Activo</th></tr></thead>
            <tbody>
              {treatments.map((t) => (
                <tr key={t.id}>
                  <td style={{ fontWeight: 600 }}>{t.name}</td>
                  <td>{t.specialty_name}</td>
                  <td className="tabular">{money(t.base_price)}</td>
                  <td>{t.is_active ? <span className="badge badge-ok">Sí</span> : <span className="badge badge-danger">No</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/* ── Especialidades ── */
function SpecialtiesTab() {
  const [specialties, setSpecialties] = useState([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/specialties/");
      const data = await resp.json();
      setSpecialties(data.results || data);
    } catch { setError("No se pudieron cargar las especialidades."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api("/specialties/", { method: "POST", body: JSON.stringify({ name }) });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : `Error ${resp.status}`);
      }
      setName("");
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      <form onSubmit={submit} style={{ display: "flex", gap: 10, marginBottom: 18, maxWidth: 460 }}>
        <input required placeholder="Nueva especialidad…" value={name}
               onChange={(e) => setName(e.target.value)}
               style={{ flex: 1, padding: "10px 12px", border: "1px solid var(--line)", borderRadius: "var(--radius)" }} />
        <button className="btn btn-primary">Agregar</button>
      </form>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>Especialidad</th><th>Activa</th></tr></thead>
          <tbody>
            {specialties.map((s) => (
              <tr key={s.id}>
                <td style={{ fontWeight: 600 }}>{s.name}</td>
                <td>{s.is_active ? <span className="badge badge-ok">Sí</span> : <span className="badge badge-danger">No</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Parámetros ── */
function ParametersTab() {
  const [params, setParams] = useState([]);
  const [editing, setEditing] = useState(null);
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/config/parameters/");
      const data = await resp.json();
      setParams(data.results || data);
    } catch { setError("No se pudieron cargar los parámetros."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function save(p) {
    setError("");
    try {
      const resp = await api(`/config/parameters/${p.id}/`, {
        method: "PATCH", body: JSON.stringify({ value }),
      });
      if (!resp.ok) throw new Error(`No se pudo guardar (error ${resp.status}).`);
      setEditing(null);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
        Estos parámetros controlan reglas del sistema (morosidad, recordatorios, alertas)
        sin necesidad de cambios de código.
      </p>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>Parámetro</th><th>Valor</th><th></th></tr></thead>
          <tbody>
            {params.map((p) => (
              <tr key={p.id}>
                <td>
                  <div style={{ fontWeight: 600 }}>{PARAM_LABELS[p.key] || p.key}</div>
                  <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{p.key}</div>
                </td>
                <td className="tabular" style={{ width: 180 }}>
                  {editing === p.id ? (
                    <input value={value} onChange={(e) => setValue(e.target.value)}
                           style={{ width: 100, padding: "6px 8px", border: "1px solid var(--line)", borderRadius: 8 }} />
                  ) : <strong>{p.value}</strong>}
                </td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {editing === p.id ? (
                    <>
                      <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                              onClick={() => save(p)}>Guardar</button>
                      <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12, marginLeft: 6 }}
                              onClick={() => setEditing(null)}>Cancelar</button>
                    </>
                  ) : (
                    <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }}
                            onClick={() => { setEditing(p.id); setValue(p.value); }}>Editar</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* ── Usuarios de staff ── */
const ROLE_OPTIONS = {
  doctor: "Doctor/a", reception: "Recepción",
  auxiliary: "Auxiliar", admin: "Administrador",
};

function UsersTab() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ full_name: "", email: "", role: "doctor", password: "" });
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/users/");
      const data = await resp.json();
      setUsers(data.results || data);
    } catch { setError("No se pudieron cargar los usuarios."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(e) {
    e.preventDefault();
    setError(""); setOkMsg("");
    try {
      const resp = await api("/users/", { method: "POST", body: JSON.stringify(form) });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : `Error ${resp.status}`);
      }
      setOkMsg(form.role === "doctor"
        ? `Usuario creado. ${form.full_name} ya aparece como doctor en la Agenda.`
        : "Usuario creado.");
      setForm({ full_name: "", email: "", role: "doctor", password: "" });
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      {okMsg && (
        <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>
          ✓ {okMsg}
        </div>
      )}

      <form onSubmit={submit} className="card" style={{ marginBottom: 18 }}>
        <h3 style={{ marginBottom: 4 }}>Nuevo usuario de staff</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Si el rol es Doctor/a, su perfil de agenda se crea automáticamente.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr 1fr auto", gap: "0 12px", alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Nombre completo *</label>
            <input required value={form.full_name}
                   onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Correo *</label>
            <input type="email" required value={form.email}
                   onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Rol *</label>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {Object.entries(ROLE_OPTIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Contraseña * (10+)</label>
            <input type="password" required minLength={10} value={form.password}
                   onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          <button className="btn btn-primary">Crear</button>
        </div>
      </form>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Activo</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td style={{ fontWeight: 600 }}>{u.full_name || "—"}</td>
                <td>{u.email}</td>
                <td><span className="badge badge-ok">{ROLE_OPTIONS[u.role] || u.role}</span></td>
                <td>{u.is_active ? "Sí" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
