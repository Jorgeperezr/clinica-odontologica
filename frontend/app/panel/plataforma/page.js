"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { useConfirm } from "../../../lib/ConfirmDialog";

const TABS = [
  ["dashboard", "Dashboard"], ["clinicas", "Clínicas"],
  ["admins", "Administradores"], ["auditoria", "Auditoría"],
  ["config", "Configuración"],
];

export default function PlataformaPage() {
  const [tab, setTab] = useState("dashboard");

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Plataforma</h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 16 }}>
        Administración del SaaS. Sin acceso a la información operativa de las clínicas.
      </p>

      <div style={{ display: "flex", gap: 4, marginBottom: 20, borderBottom: "1px solid var(--line)", flexWrap: "wrap" }}>
        {TABS.map(([k, label]) => (
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

      {tab === "dashboard" && <DashboardTab />}
      {tab === "clinicas" && <ClinicsTab />}
      {tab === "admins" && <AdminsTab />}
      {tab === "auditoria" && <AuditTab />}
      {tab === "config" && <ConfigTab />}
    </div>
  );
}

/* ───────────── 1. Dashboard ───────────── */

function DashboardTab() {
  const [data, setData] = useState(null);
  useEffect(() => {
    api("/platform/overview/").then(async (r) => r.ok && setData(await r.json())).catch(() => {});
  }, []);
  if (!data) return <div className="empty">Cargando…</div>;
  return (
    <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
      <Stat label="Clínicas registradas" value={data.clinics_total} />
      <Stat label="Activas" value={data.clinics_active} accent />
      <Stat label="Suspendidas" value={data.clinics_suspended} danger={data.clinics_suspended > 0} />
      <Stat label="Administradores de clínica" value={data.clinic_admins_total} />
    </div>
  );
}

function Stat({ label, value, accent, danger }) {
  return (
    <div className="card" style={{ flex: 1, minWidth: 170,
        ...(danger ? { borderColor: "var(--red)", background: "var(--red-soft)" } : {}) }}>
      <div style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase", letterSpacing: ".04em" }}>{label}</div>
      <div className="tabular" style={{ fontSize: 26, fontWeight: 700,
          color: danger ? "var(--red)" : accent ? "var(--petrol)" : "var(--ink)" }}>{value}</div>
    </div>
  );
}

/* ───────────── 2. Gestión de Clínicas ───────────── */

function ClinicsTab() {
  const [confirm, ConfirmUI] = useConfirm();
  const [clinics, setClinics] = useState([]);
  const [form, setForm] = useState({ name: "", ruc: "", address: "", phone: "", email: "" });
  const [editing, setEditing] = useState(null);   // clínica en edición
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/platform/clinics/");
      const data = await resp.json();
      if (!resp.ok) throw new Error();
      setClinics(data.results || data);
    } catch { setError("No se pudieron cargar las clínicas."); }
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
      setOkMsg(`Clínica "${form.name}" creada (activa, con catálogo base). Asígnale su administrador en la pestaña Administradores.`);
      setForm({ name: "", ruc: "", address: "", phone: "", email: "" });
      load();
    } catch (err) { setError(err.message); }
  }

  async function saveEdit(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api(`/platform/clinics/${editing.id}/`, {
        method: "PATCH", body: JSON.stringify(editing),
      });
      if (!resp.ok) throw new Error(`No se pudo guardar (error ${resp.status}).`);
      setEditing(null);
      load();
    } catch (err) { setError(err.message); }
  }

  async function toggleActive(clinic) {
    const action = clinic.is_active ? "Suspender" : "Activar";
    const ok = await confirm({
      title: `${action} ${clinic.name}`,
      message: clinic.is_active
        ? "Los usuarios de esta clínica perderán el acceso de inmediato. Los datos NO se borran."
        : "Los usuarios de esta clínica recuperan el acceso.",
      confirmLabel: action, danger: clinic.is_active,
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

  const fld = (k, label, type = "text") => (
    <div className="field" style={{ marginBottom: 0 }}>
      <label>{label}</label>
      <input type={type} value={editing ? (editing[k] || "") : form[k]}
             required={k === "name"}
             onChange={(e) => editing
               ? setEditing({ ...editing, [k]: e.target.value })
               : setForm({ ...form, [k]: e.target.value })} />
    </div>
  );

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      <form onSubmit={editing ? saveEdit : createClinic} className="card"
            style={{ marginBottom: 18, ...(editing ? { borderColor: "var(--petrol)" } : {}) }}>
        <h3 style={{ marginBottom: 12 }}>{editing ? `Editar — ${editing.name}` : "Registrar nueva clínica"}</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1.5fr", gap: "12px 14px" }}>
          {fld("name", "Nombre *")}
          {fld("ruc", "RUC")}
          {fld("address", "Dirección")}
          {fld("phone", "Teléfono")}
          {fld("email", "Correo", "email")}
          <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
            <button className="btn btn-primary">{editing ? "Guardar cambios" : "Crear clínica"}</button>
            {editing && (
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>Cancelar</button>
            )}
          </div>
        </div>
      </form>

      <div className="card" style={{ padding: 0 }}>
        {clinics.length === 0 ? <div className="empty">Sin clínicas registradas.</div> : (
          <table>
            <thead>
              <tr><th>Clínica</th><th>RUC</th><th>Contacto</th><th>Estado</th><th>Creada</th><th></th></tr>
            </thead>
            <tbody>
              {clinics.map((c) => (
                <tr key={c.id} style={c.is_active ? {} : { opacity: 0.65 }}>
                  <td style={{ fontWeight: 600 }}>{c.name}</td>
                  <td className="tabular">{c.ruc || "—"}</td>
                  <td style={{ fontSize: 13 }}>{c.phone || "—"}{c.email ? ` · ${c.email}` : ""}</td>
                  <td>{c.is_active
                    ? <span className="badge badge-ok">Activa</span>
                    : <span className="badge badge-danger">Suspendida</span>}</td>
                  <td className="tabular">{(c.created_at || "").slice(0, 10)}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => setEditing({ id: c.id, name: c.name, ruc: c.ruc,
                              address: c.address, phone: c.phone, email: c.email })}>Editar</button>
                    <button className="btn btn-ghost"
                            style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6,
                                     color: c.is_active ? "var(--red)" : "var(--petrol)" }}
                            onClick={() => toggleActive(c)}>
                      {c.is_active ? "Suspender" : "Activar"}
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

/* ───────────── 3. Administradores de Clínicas ───────────── */

function AdminsTab() {
  const [confirm, ConfirmUI] = useConfirm();
  const [clinics, setClinics] = useState([]);
  const [creatingFor, setCreatingFor] = useState(null);
  const [tempCred, setTempCred] = useState(null);  // {email, temporary_password}
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/platform/clinics/");
      const data = await resp.json();
      setClinics(data.results || data);
    } catch { setError("No se pudieron cargar las clínicas."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function resetPassword(clinic) {
    const ok = await confirm({
      title: `Restablecer contraseña — ${clinic.name}`,
      message: `Se generará una contraseña temporal para ${clinic.admin.email}. La actual dejará de funcionar.`,
      confirmLabel: "Restablecer", danger: true,
    });
    if (!ok) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/reset-password/`, { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setTempCred(data);
    } catch (err) { setError(err.message); }
  }

  async function toggleAdmin(clinic) {
    const active = clinic.admin.is_active;
    const ok = await confirm({
      title: `${active ? "Desactivar" : "Activar"} cuenta — ${clinic.admin.email}`,
      message: active
        ? "El administrador no podrá iniciar sesión hasta reactivarlo."
        : "El administrador recupera el acceso.",
      confirmLabel: active ? "Desactivar" : "Activar", danger: active,
    });
    if (!ok) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "PATCH", body: JSON.stringify({ is_active: !active }),
      });
      if (!resp.ok) throw new Error(`Error ${resp.status}`);
      load();
    } catch (err) { setError(err.message); }
  }

  async function updateEmail(clinic) {
    const nuevo = window.prompt(`Nuevo correo para el administrador de ${clinic.name}:`, clinic.admin.email);
    if (!nuevo || nuevo === clinic.admin.email) return;
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "PATCH", body: JSON.stringify({ email: nuevo }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}

      {tempCred && (
        <div className="card" style={{ marginBottom: 18, borderColor: "var(--amber)", background: "var(--amber-soft)" }}>
          <h3 style={{ marginBottom: 6 }}>Contraseña temporal generada</h3>
          <p style={{ fontSize: 14, marginBottom: 8 }}>
            Para <strong>{tempCred.email}</strong> — cópiala AHORA, no se puede volver a consultar:
          </p>
          <code className="tabular" style={{ fontSize: 18, fontWeight: 700, background: "#fff",
                padding: "8px 14px", borderRadius: 8, display: "inline-block" }}>
            {tempCred.temporary_password}
          </code>
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-ghost" style={{ fontSize: 13 }}
                    onClick={() => { navigator.clipboard.writeText(tempCred.temporary_password); }}>
              Copiar
            </button>
            <button className="btn btn-ghost" style={{ fontSize: 13, marginLeft: 6 }}
                    onClick={() => setTempCred(null)}>Cerrar</button>
          </div>
        </div>
      )}

      {creatingFor && (
        <CreateAdminForm clinic={creatingFor}
                         onClose={() => setCreatingFor(null)}
                         onSaved={() => { setCreatingFor(null); load(); }} />
      )}

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Clínica</th><th>Administrador</th><th>Correo</th><th>Cuenta</th><th></th></tr>
          </thead>
          <tbody>
            {clinics.map((c) => (
              <tr key={c.id}>
                <td style={{ fontWeight: 600 }}>{c.name}</td>
                <td>{c.admin ? c.admin.full_name : <span style={{ color: "var(--ink-soft)" }}>Sin asignar</span>}</td>
                <td>{c.admin?.email || "—"}</td>
                <td>{c.admin
                  ? (c.admin.is_active
                      ? <span className="badge badge-ok">Activa</span>
                      : <span className="badge badge-danger">Desactivada</span>)
                  : "—"}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {c.admin ? (
                    <>
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                              onClick={() => resetPassword(c)}>Restablecer contraseña</button>
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6 }}
                              onClick={() => updateEmail(c)}>Correo</button>
                      <button className="btn btn-ghost"
                              style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6,
                                       color: c.admin.is_active ? "var(--red)" : "var(--petrol)" }}
                              onClick={() => toggleAdmin(c)}>
                        {c.admin.is_active ? "Desactivar" : "Activar"}
                      </button>
                    </>
                  ) : (
                    <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                            onClick={() => setCreatingFor(c)}>+ Crear administrador</button>
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

function CreateAdminForm({ clinic, onClose, onSaved }) {
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
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      onSaved();
    } catch (err) { setError(err.message); }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 18, borderColor: "var(--petrol)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h3>Administrador para {clinic.name}</h3>
        <button type="button" className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }} onClick={onClose}>✕</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr 1fr auto", gap: "0 12px", alignItems: "end" }}>
        <div className="field" style={{ marginBottom: 0 }}><label>Nombre completo *</label>
          <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Correo *</label>
          <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Contraseña * (10+)</label>
          <input type="password" required minLength={10} value={form.password}
                 onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
        <button className="btn btn-primary">Crear</button>
      </div>
    </form>
  );
}

/* ───────────── 4. Auditoría ───────────── */

const ACTION_LABELS = {
  create_clinic: "Creó clínica", update_clinic: "Editó clínica",
  activate_clinic: "Activó clínica", deactivate_clinic: "Suspendió clínica",
  create_clinic_admin: "Creó administrador", update_clinic_admin: "Actualizó administrador",
  reset_clinic_admin_password: "Restableció contraseña", update_platform_config: "Cambió configuración",
};

function AuditTab() {
  const [logs, setLogs] = useState(null);
  useEffect(() => {
    api("/platform/audit/").then(async (r) => {
      if (r.ok) { const d = await r.json(); setLogs(d.results || []); }
    }).catch(() => setLogs([]));
  }, []);

  if (logs === null) return <div className="empty">Cargando…</div>;

  return (
    <div className="card" style={{ padding: 0 }}>
      {logs.length === 0 ? (
        <div className="empty">Sin acciones registradas todavía.</div>
      ) : (
        <table>
          <thead><tr><th>Fecha y hora</th><th>Usuario</th><th>Acción</th><th>Detalle</th></tr></thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id}>
                <td className="tabular" style={{ whiteSpace: "nowrap" }}>
                  {l.created_at.slice(0, 10)} {l.created_at.slice(11, 16)}
                </td>
                <td>{l.user}</td>
                <td><span className="badge badge-ok">{ACTION_LABELS[l.action] || l.action}</span></td>
                <td style={{ fontSize: 13, color: "var(--ink-soft)" }}>
                  {l.metadata?.name || l.metadata?.clinic || l.metadata?.email || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ───────────── 5. Configuración General ───────────── */

function ConfigTab() {
  const [config, setConfig] = useState(null);
  const [smtpPassword, setSmtpPassword] = useState("");
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  useEffect(() => {
    api("/platform/config/").then(async (r) => r.ok && setConfig(await r.json())).catch(() => {});
  }, []);

  if (!config) return <div className="empty">Cargando…</div>;

  async function save(e) {
    e.preventDefault();
    setError(""); setOkMsg("");
    try {
      const body = { ...config };
      delete body.smtp_password_set;
      delete body.updated_at;
      if (smtpPassword) body.smtp_password = smtpPassword;
      const resp = await api("/platform/config/", { method: "PATCH", body: JSON.stringify(body) });
      const data = await resp.json();
      if (!resp.ok) throw new Error(`No se pudo guardar (error ${resp.status}).`);
      setConfig(data);
      setSmtpPassword("");
      setOkMsg("Configuración guardada.");
    } catch (err) { setError(err.message); }
  }

  const fld = (k, label, type = "text") => (
    <div className="field" style={{ marginBottom: 0 }}>
      <label>{label}</label>
      <input type={type} value={config[k] ?? ""}
             onChange={(e) => setConfig({ ...config, [k]: e.target.value })} />
    </div>
  );

  return (
    <form onSubmit={save}>
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12 }}>Identidad de la plataforma</h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 14px" }}>
          {fld("platform_name", "Nombre de la plataforma")}
          {fld("logo_url", "URL del logo")}
          {fld("timezone", "Zona horaria")}
          {fld("currency", "Moneda")}
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginBottom: 4 }}>Correo saliente (SMTP)</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Para notificaciones por correo de la plataforma.
          {config.smtp_password_set && " Hay una contraseña guardada (no se muestra)."}
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "12px 14px" }}>
          {fld("smtp_host", "Servidor SMTP")}
          {fld("smtp_port", "Puerto", "number")}
          {fld("smtp_user", "Usuario")}
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Contraseña {config.smtp_password_set ? "(dejar vacío para no cambiar)" : ""}</label>
            <input type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} />
          </div>
        </div>
      </div>

      <button className="btn btn-primary">Guardar configuración</button>
    </form>
  );
}
