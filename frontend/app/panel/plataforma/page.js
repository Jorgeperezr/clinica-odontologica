"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { useConfirm } from "../../../lib/ConfirmDialog";

export default function PlataformaPage() {
  const [confirm, ConfirmUI] = useConfirm();
  const [overview, setOverview] = useState(null);
  const [clinics, setClinics] = useState([]);
  const [form, setForm] = useState({ name: "", ruc: "" });
  const [adminFor, setAdminFor] = useState(null); // clínica a la que se crea admin
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const [oResp, cResp] = await Promise.all([
        api("/platform/overview/"), api("/platform/clinics/"),
      ]);
      setOverview(await oResp.json());
      const c = await cResp.json();
      setClinics(c.results || c);
    } catch { setError("No se pudo cargar la información de la plataforma."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createClinic(e) {
    e.preventDefault();
    setError(""); setOkMsg("");
    try {
      const resp = await api("/platform/clinics/", { method: "POST", body: JSON.stringify(form) });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : `Error ${resp.status}`);
      }
      setOkMsg(`Clínica "${form.name}" creada con su catálogo base (especialidades, parámetros y odontograma). Ahora creale su Administrador con el botón "+ Admin".`);
      setForm({ name: "", ruc: "" });
      load();
    } catch (err) { setError(err.message); }
  }

  async function toggleActive(clinic) {
    const action = clinic.is_active ? "Desactivar" : "Activar";
    const ok = await confirm({
      title: `${action} ${clinic.name}`,
      message: clinic.is_active
        ? "Todos los usuarios de esta clínica perderán el acceso de inmediato (incluso con sesión abierta). Los datos NO se borran."
        : "Los usuarios de esta clínica recuperan el acceso.",
      confirmLabel: action,
      danger: clinic.is_active,
    });
    if (!ok) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/`, {
        method: "PATCH", body: JSON.stringify({ is_active: !clinic.is_active }),
      });
      if (!resp.ok) throw new Error(`No se pudo actualizar (error ${resp.status}).`);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Plataforma</h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 20 }}>
        Gestión de las clínicas del sistema (Super Administrador).
      </p>

      {error && <div className="error-box">{error}</div>}
      {okMsg && (
        <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>
          ✓ {okMsg}
        </div>
      )}

      {/* Indicadores globales */}
      {overview && (
        <div style={{ display: "flex", gap: 14, marginBottom: 22, flexWrap: "wrap" }}>
          <Stat label="Clínicas" value={overview.clinics_total} />
          <Stat label="Activas" value={overview.clinics_active} accent />
          <Stat label="Staff total" value={overview.staff_total} />
          <Stat label="Pacientes totales" value={overview.patients_total} />
        </div>
      )}

      {/* Nueva clínica */}
      <form onSubmit={createClinic} className="card" style={{ marginBottom: 18 }}>
        <h3 style={{ marginBottom: 12 }}>Nueva clínica</h3>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr auto", gap: "0 12px", alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Nombre *</label>
            <input required value={form.name}
                   onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>RUC</label>
            <input value={form.ruc}
                   onChange={(e) => setForm({ ...form, ruc: e.target.value })} /></div>
          <button className="btn btn-primary">Crear clínica</button>
        </div>
      </form>

      {adminFor && (
        <AdminForm clinic={adminFor}
                   onClose={() => setAdminFor(null)}
                   onSaved={(msg) => { setAdminFor(null); setOkMsg(msg); load(); }} />
      )}

      {/* Listado de clínicas */}
      <div className="card" style={{ padding: 0 }}>
        {clinics.length === 0 ? (
          <div className="empty">Sin clínicas registradas. Crea la primera.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Clínica</th><th>RUC</th><th>Staff</th><th>Pacientes</th><th>Estado</th><th>Creada</th><th></th></tr>
            </thead>
            <tbody>
              {clinics.map((c) => (
                <tr key={c.id} style={c.is_active ? {} : { opacity: 0.6 }}>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td className="tabular">{c.ruc || "—"}</td>
                  <td className="tabular">{c.staff_count}</td>
                  <td className="tabular">{c.patient_count}</td>
                  <td>{c.is_active
                    ? <span className="badge badge-ok">Activa</span>
                    : <span className="badge badge-danger">Desactivada</span>}</td>
                  <td className="tabular">{(c.created_at || "").slice(0, 10)}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => setAdminFor(c)}>+ Admin</button>
                    <button className="btn btn-ghost"
                            style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6,
                                     color: c.is_active ? "var(--red)" : "var(--petrol)" }}
                            onClick={() => toggleActive(c)}>
                      {c.is_active ? "Desactivar" : "Activar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 140 }}>
      <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>{label}</div>
      <div className="tabular" style={{ fontSize: 24, fontWeight: 700, color: accent ? "var(--petrol)" : "var(--ink)" }}>{value}</div>
    </div>
  );
}

function AdminForm({ clinic, onClose, onSaved }) {
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "POST", body: JSON.stringify(form),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const detail = data?.error?.details || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : `Error ${resp.status}`);
      }
      onSaved(`Administrador ${form.full_name} creado para ${clinic.name}. Ya puede entrar al panel con su correo y contraseña.`);
    } catch (err) { setError(err.message); }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 18, borderColor: "var(--petrol)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h3>Nuevo Administrador — {clinic.name}</h3>
        <button type="button" className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }} onClick={onClose}>✕</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr auto", gap: "0 12px", alignItems: "end" }}>
        <div className="field" style={{ marginBottom: 0 }}><label>Nombre completo *</label>
          <input required value={form.full_name}
                 onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Correo *</label>
          <input type="email" required value={form.email}
                 onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Contraseña * (10+)</label>
          <input type="password" required minLength={10} value={form.password}
                 onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
        <button className="btn btn-primary">Crear</button>
      </div>
    </form>
  );
}
