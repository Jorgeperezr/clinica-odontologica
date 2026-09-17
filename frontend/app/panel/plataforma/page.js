"use client";

import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage, readList } from "../../../lib/api";
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
  // `error` separado de `data` a propósito: sin él, `r.ok && setData(...)`
  // se traga el fallo y la pantalla se queda diciendo «Cargando…» para
  // siempre. Pasa de verdad —entrar aquí con un usuario que administra
  // una clínica da 403, porque esto es del superadministrador— y quien lo
  // ve no tiene forma de saber si está cargando, si se cayó algo o si no
  // le corresponde entrar.
  const [error, setError] = useState("");
  useEffect(() => {
    api("/platform/overview/")
      .then(async (r) => (r.ok ? setData(await r.json()) : setError(await apiErrorMessage(r))))
      .catch(() => setError("No se pudo contactar con el servidor."));
  }, []);
  if (error) return <div className="error-box">{error}</div>;
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

/* ───────────── Entrega de credenciales ───────────── */

/**
 * La contraseña temporal, una sola vez, y lo que hay que hacer con ella.
 *
 * Lo que de verdad resuelve es el paso siguiente: el dueño de la
 * plataforma tiene que HACER LLEGAR esto a la clínica. Copiar la
 * contraseña suelta obliga a redactar el resto a mano cada vez —dónde se
 * entra, con qué correo, que hay que cambiarla— y ahí es donde se pierde
 * la mitad del mensaje. El botón de abajo copia la nota entera, lista
 * para pegar en un correo o en WhatsApp.
 */
function PanelDeCredenciales({ cred, clinica, onClose }) {
  const [copiado, setCopiado] = useState("");

  const url = typeof window !== "undefined" ? `${window.location.origin}/login/` : "";
  const nota = [
    `Acceso al sistema de ${clinica || "su clínica"}`,
    "",
    `Dirección: ${url}`,
    `Usuario: ${cred.email}`,
    `Contraseña temporal: ${cred.temporary_password}`,
    "",
    "Al entrar por primera vez el sistema le pedirá elegir su propia",
    "contraseña. Desde ese momento nadie más que usted la conoce, y",
    "podrá registrar a los profesionales de la clínica desde",
    "Configuración → Usuarios.",
  ].join("\n");

  async function copiar(texto, cual) {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(cual);
      setTimeout(() => setCopiado(""), 2000);
    } catch {
      // Sin permiso de portapapeles (o sin HTTPS) no se puede copiar; la
      // contraseña está a la vista, que es lo que importa.
      setCopiado("no");
    }
  }

  return (
    <div className="card" style={{ marginBottom: 18, borderColor: "var(--amber)",
                                   background: "var(--amber-soft)" }}>
      <h3 style={{ marginBottom: 4 }}>
        Credenciales de {clinica ? <>«{clinica}»</> : "la clínica"} — entrégalas ahora
      </h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
        Esta contraseña <strong>no se puede volver a consultar</strong>: no queda
        guardada en ningún sitio. Solo sirve para el primer ingreso; al entrar,
        la clínica elige la suya y tú dejas de tener acceso a la cuenta.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 14px",
                    alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase",
                       letterSpacing: ".04em" }}>Usuario</span>
        <code style={{ fontSize: 15, background: "var(--elev)", padding: "6px 12px",
                       borderRadius: 8, justifySelf: "start" }}>{cred.email}</code>

        <span style={{ fontSize: 12, color: "var(--ink-soft)", textTransform: "uppercase",
                       letterSpacing: ".04em" }}>Contraseña</span>
        <code className="tabular" style={{ fontSize: 18, fontWeight: 700, background: "var(--elev)",
                       padding: "6px 12px", borderRadius: 8, justifySelf: "start",
                       letterSpacing: ".02em" }}>{cred.temporary_password}</code>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn btn-primary" style={{ fontSize: 13 }}
                onClick={() => copiar(nota, "nota")}>
          Copiar mensaje de entrega
        </button>
        <button className="btn btn-ghost" style={{ fontSize: 13 }}
                onClick={() => copiar(cred.temporary_password, "clave")}>
          Copiar solo la contraseña
        </button>
        <button className="btn btn-ghost" style={{ fontSize: 13, marginLeft: "auto" }}
                onClick={onClose}>Ya la entregué</button>
      </div>

      {copiado === "nota" && <p style={{ fontSize: 13, marginTop: 8, color: "var(--petrol-deep)" }}>✓ Mensaje copiado.</p>}
      {copiado === "clave" && <p style={{ fontSize: 13, marginTop: 8, color: "var(--petrol-deep)" }}>✓ Contraseña copiada.</p>}
      {copiado === "no" && <p style={{ fontSize: 13, marginTop: 8, color: "var(--red)" }}>
        El navegador no dejó copiar. Selecciónala a mano, arriba.</p>}
    </div>
  );
}

/* ───────────── 2. Gestión de Clínicas ───────────── */

function ClinicsTab() {
  const [confirm, ConfirmUI] = useConfirm();
  const [clinics, setClinics] = useState([]);
  const VACIO = { name: "", ruc: "", address: "", phone: "", email: "",
                  admin_full_name: "", admin_email: "" };
  const [form, setForm] = useState(VACIO);
  const [editing, setEditing] = useState(null);   // clínica en edición
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [cred, setCred] = useState(null);         // {email, temporary_password, clinica}

  const load = useCallback(async () => {
    try {
      setClinics(await readList(await api("/platform/clinics/")));
    } catch (err) { setError(err?.message ? `No se pudieron cargar las clínicas. ${err.message}` : "No se pudieron cargar las clínicas."); }
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
      // El alta del administrador va en la misma respuesta, y puede
      // traer su propio error sin que eso deshaga la clínica: un correo
      // repetido no es motivo para cancelar un alta que ya está hecha.
      const alta = data.admin;
      if (alta?.temporary_password) {
        setCred({ ...alta, clinica: form.name });
        setOkMsg(`Clínica "${form.name}" creada con su administrador. Entrégale las credenciales de abajo.`);
      } else if (alta?.error) {
        setOkMsg("");
        setError(`La clínica "${form.name}" se creó, pero su administrador no: ${alta.error} `
                 + "Créalo desde la pestaña Administradores.");
      } else {
        setOkMsg(`Clínica "${form.name}" creada (activa, con catálogo base). `
                 + "Aún no tiene administrador: créalo en la pestaña Administradores.");
      }
      setForm(VACIO);
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

      {cred && (
        <PanelDeCredenciales cred={cred} clinica={cred.clinica} onClose={() => setCred(null)} />
      )}

      <form onSubmit={editing ? saveEdit : createClinic} className="card"
            style={{ marginBottom: 18, ...(editing ? { borderColor: "var(--petrol)" } : {}) }}>
        <h3 style={{ marginBottom: 2 }}>{editing ? `Editar — ${editing.name}` : "Registrar nueva clínica"}</h3>
        {!editing && (
          <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
            La clínica queda activa y con el catálogo base. Si indicas su
            administrador aquí, al guardar se genera su contraseña y se
            muestra una sola vez para que se la entregues.
          </p>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1.5fr", gap: "12px 14px" }}>
          {fld("name", "Nombre *")}
          {fld("ruc", "RUC")}
          {fld("address", "Dirección")}
          {fld("phone", "Teléfono")}
          {fld("email", "Correo", "email")}
          {editing && (
            <div style={{ display: "flex", gap: 8, alignItems: "end" }}>
              <button className="btn btn-primary">Guardar cambios</button>
              <button type="button" className="btn btn-ghost" onClick={() => setEditing(null)}>Cancelar</button>
            </div>
          )}
        </div>

        {/* Los datos del administrador solo al crear: al editar una
            clínica ya existente su administrador se gestiona en su
            propia pestaña, donde además se puede desactivar o cambiar. */}
        {!editing && (
          <>
            <div style={{ borderTop: "1px solid var(--line)", margin: "16px 0 14px" }} />
            <h4 style={{ marginBottom: 2, fontSize: 14 }}>Administrador de la clínica</h4>
            <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
              Es quien recibe las credenciales y, ya dentro, da de alta a los
              profesionales. Opcional: puedes crearlo más tarde.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr auto",
                          gap: "12px 14px", alignItems: "end" }}>
              {fld("admin_full_name", "Nombre completo")}
              {fld("admin_email", "Correo de acceso", "email")}
              <button className="btn btn-primary">
                {form.admin_email ? "Crear clínica y credenciales" : "Crear clínica"}
              </button>
            </div>
          </>
        )}
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
  const [editingEmail, setEditingEmail] = useState(null);   // clinic.id en edición
  const [emailDraft, setEmailDraft] = useState("");
  const [tempCred, setTempCred] = useState(null);  // {email, temporary_password}
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api("/platform/clinics/");
      setClinics(await readList(resp));
    } catch (err) { setError(err?.message ? `No se pudieron cargar las clínicas. ${err.message}` : "No se pudieron cargar las clínicas."); }
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
      setTempCred({ ...data, clinica: clinic.name });
      load();   // la cuenta vuelve a quedar pendiente de cambio
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

  async function saveEmail(clinic) {
    if (!emailDraft || emailDraft === clinic.admin.email) { setEditingEmail(null); return; }
    try {
      const resp = await api(`/platform/clinics/${clinic.id}/admin/`, {
        method: "PATCH", body: JSON.stringify({ email: emailDraft }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setEditingEmail(null);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}

      {tempCred && (
        <PanelDeCredenciales cred={tempCred} clinica={tempCred.clinica}
                             onClose={() => setTempCred(null)} />
      )}

      {creatingFor && (
        <CreateAdminForm clinic={creatingFor}
                         onClose={() => setCreatingFor(null)}
                         onSaved={(cred) => {
                           setCreatingFor(null);
                           if (cred?.temporary_password) {
                             setTempCred({ ...cred, clinica: creatingFor.name });
                           }
                           load();
                         }} />
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
                <td>
                  {editingEmail === c.id ? (
                    <span style={{ display: "inline-flex", gap: 6 }}>
                      <input type="email" value={emailDraft} autoFocus
                             onChange={(e) => setEmailDraft(e.target.value)}
                             onKeyDown={(e) => e.key === "Enter" && saveEmail(c)}
                             style={{ padding: "4px 8px", border: "1px solid var(--petrol)", borderRadius: 6, fontSize: 13 }} />
                      <button className="btn btn-primary" style={{ padding: "3px 10px", fontSize: 12 }}
                              onClick={() => saveEmail(c)}>Guardar</button>
                      <button className="btn btn-ghost" style={{ padding: "3px 8px", fontSize: 12 }}
                              onClick={() => setEditingEmail(null)}>✕</button>
                    </span>
                  ) : (c.admin?.email || "—")}
                </td>
                {/* Tres estados, no dos. «Pendiente» es el que faltaba:
                    dice que las credenciales se generaron pero la clínica
                    todavía no ha entrado a elegir la suya, así que la
                    entrega no ha terminado. Sin él, una clínica que nunca
                    ingresó se ve igual que una que lleva meses trabajando. */}
                <td>{c.admin
                  ? (!c.admin.is_active
                      ? <span className="badge badge-danger">Desactivada</span>
                      : c.admin.must_change_password
                        ? <span className="badge badge-warn"
                                title="Se le generó una contraseña temporal y aún no ha ingresado a cambiarla.">
                            Pendiente de ingreso
                          </span>
                        : <span className="badge badge-ok">Activa</span>)
                  : "—"}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {c.admin ? (
                    <>
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                              onClick={() => resetPassword(c)}>Restablecer contraseña</button>
                      <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6 }}
                              onClick={() => { setEditingEmail(c.id); setEmailDraft(c.admin.email); }}>Correo</button>
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
  const [form, setForm] = useState({ full_name: "", email: "" });
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
      onSaved(data);
    } catch (err) { setError(err.message); }
  }

  return (
    <form onSubmit={submit} className="card" style={{ marginBottom: 18, borderColor: "var(--petrol)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h3>Administrador para {clinic.name}</h3>
        <button type="button" className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }} onClick={onClose}>✕</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      {/* Ya no se pide contraseña: la genera el servidor y se muestra
          una sola vez al guardar. Pedirle a una persona que invente un
          secreto para otra es como acaban existiendo las «clinica2026». */}
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr auto", gap: "0 12px", alignItems: "end" }}>
        <div className="field" style={{ marginBottom: 0 }}><label>Nombre completo *</label>
          <input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Correo de acceso *</label>
          <input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
        <button className="btn btn-primary">Crear y generar credenciales</button>
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
  const [error, setError] = useState("");
  useEffect(() => {
    api("/platform/audit/")
      .then(async (r) => (r.ok ? setLogs(await readList(r)) : setError(await apiErrorMessage(r))))
      .catch(() => setError("No se pudo contactar con el servidor."));
  }, []);

  if (error) return <div className="error-box">{error}</div>;
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
    api("/platform/config/")
      .then(async (r) => (r.ok ? setConfig(await r.json()) : setError(await apiErrorMessage(r))))
      .catch(() => setError("No se pudo contactar con el servidor."));
  }, []);

  if (error) return <div className="error-box">{error}</div>;
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
