"use client";

import { useCallback, useEffect, useState } from "react";
import { api, apiBase } from "../../../lib/api";
import { PRESETS, applyTheme, logoSrc, resetTheme, saveBrandingCache } from "../../../lib/theme";
import LogoCropper from "../../../lib/LogoCropper";

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
        {[["tratamientos", "Tratamientos"], ["plantillas", "Plantillas de plan"], ["especialidades", "Especialidades"], ["usuarios", "Usuarios"], ["parametros", "Parámetros"], ["consentimientos", "Consentimientos"], ["personalizacion", "Personalización"]].map(([k, label]) => (
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
      {tab === "plantillas" && <TemplatesTab />}
      {tab === "usuarios" && <UsersTab />}
      {tab === "parametros" && <ParametersTab />}
      {tab === "consentimientos" && <ConsentTemplatesTab />}
      {tab === "personalizacion" && <BrandingTab />}
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
        <div className="success-box">
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


/* ── Plantillas de planes de tratamiento ── */
function TemplatesTab() {
  const [templates, setTemplates] = useState([]);
  const [treatments, setTreatments] = useState([]);
  const [form, setForm] = useState({ name: "", description: "" });
  const [addingTo, setAddingTo] = useState(null);   // template al que se agrega ítem
  const [newItem, setNewItem] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [tResp, trResp] = await Promise.all([
        api("/clinical/plan-templates/"), api("/config/treatments/?is_active=true"),
      ]);
      const t = await tResp.json(); setTemplates(t.results || t);
      const tr = await trResp.json(); setTreatments(tr.results || tr);
    } catch { setError("No se pudieron cargar las plantillas."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function createTemplate(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api("/clinical/plan-templates/", { method: "POST", body: JSON.stringify(form) });
      if (!resp.ok) throw new Error(`No se pudo crear (error ${resp.status}).`);
      setForm({ name: "", description: "" });
      load();
    } catch (err) { setError(err.message); }
  }

  async function addItem(template) {
    if (!newItem) return;
    setError("");
    try {
      const resp = await api(`/clinical/plan-templates/${template.id}/items/`, {
        method: "POST", body: JSON.stringify({ treatment: newItem }),
      });
      if (!resp.ok) throw new Error(`No se pudo agregar (error ${resp.status}).`);
      setNewItem("");
      load();
    } catch (err) { setError(err.message); }
  }

  async function removeItem(itemId) {
    try {
      const resp = await api(`/clinical/plan-template-items/${itemId}/`, { method: "DELETE" });
      if (!resp.ok && resp.status !== 204) throw new Error(`Error ${resp.status}`);
      load();
    } catch (err) { setError(err.message); }
  }

  const money = (v) => `$${Number(v || 0).toFixed(2)}`;

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
        Una plantilla agrupa tratamientos frecuentes (ej. "Ortodoncia completa").
        Desde la ficha del paciente se aplica con un clic: crea el plan con sus
        ítems y precios del tarifario, listo para generar el presupuesto.
      </p>

      <form onSubmit={createTemplate} className="card" style={{ marginBottom: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 2fr auto", gap: "0 12px", alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Nombre *</label>
            <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Descripción</label>
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <button className="btn btn-primary">Crear plantilla</button>
        </div>
      </form>

      {templates.length === 0 ? (
        <div className="card"><div className="empty">Sin plantillas. Crea la primera.</div></div>
      ) : templates.map((t) => (
        <div key={t.id} className="card" style={{ marginBottom: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div>
              <strong>{t.name}</strong>
              {t.description && <span style={{ color: "var(--ink-soft)", fontSize: 13, marginLeft: 8 }}>{t.description}</span>}
            </div>
            <span className="tabular" style={{ fontWeight: 700 }}>{money(t.total_estimated)}</span>
          </div>

          {t.items?.length > 0 && (
            <table style={{ marginTop: 10 }}>
              <thead><tr><th>#</th><th>Tratamiento</th><th>Precio base</th><th></th></tr></thead>
              <tbody>
                {t.items.map((it) => (
                  <tr key={it.id}>
                    <td className="tabular">{it.order}</td>
                    <td>{it.treatment_name}</td>
                    <td className="tabular">{money(it.base_price)}</td>
                    <td style={{ textAlign: "right" }}>
                      <button className="btn btn-ghost" style={{ padding: "3px 10px", fontSize: 12, color: "var(--red)" }}
                              onClick={() => removeItem(it.id)}>Quitar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {addingTo === t.id ? (
            <div style={{ display: "flex", gap: 8, marginTop: 10, alignItems: "center" }}>
              <select value={newItem} onChange={(e) => setNewItem(e.target.value)}
                      style={{ flex: 1, padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 8 }}>
                <option value="">Seleccionar tratamiento…</option>
                {treatments.map((tr) => (
                  <option key={tr.id} value={tr.id}>{tr.name} — {money(tr.base_price)}</option>
                ))}
              </select>
              <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => addItem(t)}>Agregar</button>
              <button className="btn btn-ghost" style={{ fontSize: 13 }}
                      onClick={() => { setAddingTo(null); setNewItem(""); }}>Cerrar</button>
            </div>
          ) : (
            <button className="btn btn-ghost" style={{ marginTop: 10, fontSize: 13 }}
                    onClick={() => setAddingTo(t.id)}>+ Agregar tratamiento</button>
          )}
        </div>
      ))}
    </div>
  );
}


/* ── Personalización (Sprint 33) ── */
function BrandingTab() {
  const [branding, setBranding] = useState(null);
  const [autoPalette, setAutoPalette] = useState(null);
  const [primary, setPrimary] = useState("#0e5c63");
  const [secondary, setSecondary] = useState("#9fe1cb");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [cropFile, setCropFile] = useState(null);      // archivo elegido, en recorte
  const [displayName, setDisplayName] = useState("");
  const [shortName, setShortName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  async function load() {
    try {
      const resp = await api("/config/branding/");
      const data = await resp.json();
      setBranding(data);
      if (data.theme?.primary) setPrimary(data.theme.primary);
      if (data.theme?.secondary) setSecondary(data.theme.secondary);
      setDisplayName(data.display_name || "");
      setShortName(data.short_name || "");
      setAddress(data.address || "");
      setPhone(data.phone || "");
      setContactEmail(data.email || "");
    } catch { setError("No se pudo cargar la personalización."); }
  }
  useEffect(() => { load(); }, []);

  async function saveTheme(theme) {
    setSaving(true); setError(""); setOkMsg("");
    try {
      const resp = await api("/config/branding/", {
        method: "PATCH", body: JSON.stringify({ theme }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setBranding(data);
      applyTheme(data.theme);
      saveBrandingCache(data);
      setOkMsg("Tema aplicado y guardado.");
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function uploadLogo(file) {
    if (!file) return;
    setSaving(true); setError(""); setOkMsg("");
    try {
      const fd = new FormData();
      fd.append("logo", file);
      // FormData: sin Content-Type manual (el navegador pone el boundary)
      const token = localStorage.getItem("access");
      const resp = await fetch(`${apiBase()}/api/v1/config/branding/`, {
        method: "PATCH",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setBranding(data);
      saveBrandingCache(data);
      setAutoPalette(data.auto_palette || null);
      setOkMsg(data.auto_palette?.primary
        ? "Logotipo guardado. Puedes aplicar sus colores como tema."
        : "Logotipo guardado.");
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function removeLogo() {
    setSaving(true); setError(""); setOkMsg("");
    try {
      const fd = new FormData();
      fd.append("logo_clear", "true");
      const token = localStorage.getItem("access");
      const resp = await fetch(`${apiBase()}/api/v1/config/branding/`, {
        method: "PATCH",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setBranding(data);
      saveBrandingCache(data);
      setAutoPalette(null);
      setOkMsg("Logotipo eliminado.");
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  async function saveNames() {
    setSaving(true); setError(""); setOkMsg("");
    try {
      const resp = await api("/config/branding/", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName, short_name: shortName,
                               address, phone, email: contactEmail }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setBranding(data);
      saveBrandingCache(data);
      setOkMsg("Datos de la clínica guardados.");
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  const currentPreset = branding?.theme?.preset || "default";

  return (
    <div style={{ display: "grid", gap: 18, maxWidth: 860 }}>
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="success-box">✓ {okMsg}</div>}

      {/* Logotipo */}
      <div className="card">
        <h3 style={{ marginBottom: 6 }}>Logotipo de la clínica</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Se muestra en la barra lateral y sirve de base para el tema automático de colores.
        </p>
        <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ width: 140, height: 90, border: "1px dashed var(--line)", borderRadius: 10,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        overflow: "hidden",
                        backgroundColor: "#fff",
                        backgroundImage: "linear-gradient(45deg, #e5e9ee 25%, transparent 25%), linear-gradient(-45deg, #e5e9ee 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #e5e9ee 75%), linear-gradient(-45deg, transparent 75%, #e5e9ee 75%)",
                        backgroundSize: "16px 16px",
                        backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0px" }}>
            {branding?.logo_url
              ? <img src={logoSrc(branding.logo_url, branding.updated_at)} alt="Vista previa del logotipo"
                     style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
              : <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>Sin logotipo</span>}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label className="btn btn-primary" style={{ cursor: "pointer", textAlign: "center" }}>
              {branding?.logo_url ? "Cambiar logotipo" : "Subir logotipo"}
              <input type="file" accept="image/*" style={{ display: "none" }}
                     onChange={(e) => { setCropFile(e.target.files?.[0] || null); e.target.value = ""; }} />
            </label>
            {branding?.logo_url && (
              <button className="btn btn-ghost" onClick={removeLogo} disabled={saving}>
                Eliminar logotipo
              </button>
            )}
          </div>
          {autoPalette?.primary && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                          borderRadius: 10, background: "var(--petrol-soft)" }}>
              <span style={{ fontSize: 13 }}>Colores del logotipo:</span>
              <span style={{ width: 22, height: 22, borderRadius: 6, background: autoPalette.primary, border: "1px solid var(--line)" }} />
              {autoPalette.secondary && (
                <span style={{ width: 22, height: 22, borderRadius: 6, background: autoPalette.secondary, border: "1px solid var(--line)" }} />
              )}
              <button className="btn btn-primary" style={{ fontSize: 13 }} disabled={saving}
                      onClick={() => saveTheme({ preset: "auto",
                                                 primary: autoPalette.primary,
                                                 secondary: autoPalette.secondary || "" })}>
                Usar como tema
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Nombre de la clínica */}
      <div className="card">
        <h3 style={{ marginBottom: 6 }}>Nombre de la clínica</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          Reemplaza el texto "Clínica" en la barra lateral, el título de la ventana y los encabezados.
        </p>
        <div style={{ display: "flex", gap: 14, alignItems: "end", flexWrap: "wrap" }}>
          <div className="field" style={{ marginBottom: 0, flex: "1 1 240px" }}>
            <label>Nombre comercial</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                   placeholder="Ej: Clínica Dental Sonrisa Sana" maxLength={120} />
          </div>
          <div className="field" style={{ marginBottom: 0, flex: "0 1 200px" }}>
            <label>Nombre corto (opcional)</label>
            <input value={shortName} onChange={(e) => setShortName(e.target.value)}
                   placeholder="Ej: Sonrisa Sana" maxLength={40} />
          </div>
          <button className="btn btn-primary" disabled={saving} onClick={saveNames}>
            Guardar datos
          </button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1.5fr", gap: 14, marginTop: 14 }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Dirección</label>
            <input value={address} onChange={(e) => setAddress(e.target.value)}
                   placeholder="Av. Principal 123 y Secundaria" maxLength={200} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Teléfono</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)}
                   placeholder="0999999999" maxLength={40} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Correo electrónico</label>
            <input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)}
                   placeholder="info@clinica.ec" />
          </div>
        </div>
        <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 10 }}>
          Estos datos aparecen en el encabezado y pie de los documentos (solicitudes de examen, etc.).
        </p>
      </div>

      {/* Temas predefinidos */}
      <div className="card">
        <h3 style={{ marginBottom: 6 }}>Tema de colores</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 12 }}>
          El color elegido se ajusta automáticamente para garantizar buen contraste y legibilidad.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
          {PRESETS.map((p) => (
            <button key={p.key} disabled={saving}
                    onClick={() => saveTheme({ preset: p.key, primary: "", secondary: "" })}
                    style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px",
                             borderRadius: 10, cursor: "pointer", fontSize: 13, background: "var(--elev)",
                             border: currentPreset === p.key
                               ? "2px solid var(--petrol)" : "1px solid var(--line)",
                             fontWeight: currentPreset === p.key ? 700 : 400 }}>
              <span style={{ width: 18, height: 18, borderRadius: "50%", background: p.primary }} />
              <span style={{ width: 18, height: 18, borderRadius: "50%", background: p.secondary }} />
              {p.label}
            </button>
          ))}
        </div>

        {/* Personalización manual */}
        <div style={{ display: "flex", gap: 16, alignItems: "end", flexWrap: "wrap" }}>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Color principal</label>
            <input type="color" value={primary} onChange={(e) => setPrimary(e.target.value)}
                   style={{ width: 64, height: 38, padding: 2, border: "1px solid var(--line)", borderRadius: 8 }} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label>Color secundario</label>
            <input type="color" value={secondary} onChange={(e) => setSecondary(e.target.value)}
                   style={{ width: 64, height: 38, padding: 2, border: "1px solid var(--line)", borderRadius: 8 }} />
          </div>
          <button className="btn btn-primary" disabled={saving}
                  onClick={() => saveTheme({ preset: "custom", primary, secondary })}>
            Aplicar colores
          </button>
          <button className="btn btn-ghost" disabled={saving}
                  onClick={() => { resetTheme(); saveTheme({ preset: "default", primary: "", secondary: "" }); }}>
            Restablecer tema del sistema
          </button>
        </div>
      </div>
      {cropFile && (
        <LogoCropper file={cropFile}
                     onCancel={() => setCropFile(null)}
                     onConfirm={(finalFile) => { setCropFile(null); uploadLogo(finalFile); }} />
      )}
    </div>
  );
}


/* ── Plantillas de consentimiento (Sprint 37) ── */
const PROCEDURES = [
  ["extraccion", "Extracción dental"], ["endodoncia", "Endodoncia"],
  ["restauracion", "Restauración"], ["profilaxis", "Profilaxis"],
  ["cirugia", "Cirugía oral"], ["implante", "Implante"],
  ["protesis", "Prótesis"], ["ortodoncia", "Ortodoncia"], ["otro", "Otro"],
];

function ConsentTemplatesTab() {
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);   // objeto en edición o null
  const [error, setError] = useState("");

  async function load() {
    try {
      const resp = await api("/consent-templates/");
      const data = await resp.json();
      setTemplates(data.results || data);
    } catch { setError("No se pudieron cargar las plantillas."); }
  }
  useEffect(() => { load(); }, []);

  function blank() {
    return { procedure: "extraccion", title: "", procedure_text: "",
             benefits: "", risks: "", alternatives: "", body_text: "" };
  }

  async function save() {
    setError("");
    try {
      const isNew = !editing.id;
      const resp = await api(
        isNew ? "/consent-templates/" : `/consent-templates/${editing.id}/`,
        { method: isNew ? "POST" : "PATCH", body: JSON.stringify(editing) }
      );
      if (!resp.ok) throw new Error(`No se pudo guardar (error ${resp.status}).`);
      setEditing(null);
      load();
    } catch (err) { setError(err.message); }
  }

  async function remove(t) {
    if (!window.confirm(`¿Eliminar la plantilla "${t.title}"?`)) return;
    try {
      const resp = await api(`/consent-templates/${t.id}/`, { method: "DELETE" });
      if (!resp.ok && resp.status !== 204) throw new Error(`Error ${resp.status}`);
      load();
    } catch (err) { setError(err.message); }
  }

  return (
    <div style={{ maxWidth: 860 }}>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <p style={{ fontSize: 14, color: "var(--ink-soft)", margin: 0 }}>
          Plantillas reutilizables de consentimiento, clasificadas por procedimiento.
        </p>
        {!editing && (
          <button className="btn btn-primary" onClick={() => setEditing(blank())}>+ Nueva plantilla</button>
        )}
      </div>

      {editing && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 12, marginBottom: 12 }}>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Procedimiento</label>
              <select value={editing.procedure} onChange={(e) => setEditing({ ...editing, procedure: e.target.value })}>
                {PROCEDURES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="field" style={{ marginBottom: 0 }}>
              <label>Título</label>
              <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })}
                     placeholder="Ej: Consentimiento para extracción simple" />
            </div>
          </div>
          {[["procedure_text", "Descripción del procedimiento"], ["benefits", "Beneficios"],
            ["risks", "Riesgos y complicaciones"], ["alternatives", "Alternativas"],
            ["body_text", "Declaración de aceptación"]].map(([k, label]) => (
            <div className="field" key={k}>
              <label>{label}</label>
              <textarea rows={2} value={editing[k] || ""}
                        onChange={(e) => setEditing({ ...editing, [k]: e.target.value })} />
            </div>
          ))}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-primary" onClick={save}>Guardar plantilla</button>
            <button className="btn btn-ghost" onClick={() => setEditing(null)}>Cancelar</button>
          </div>
        </div>
      )}

      {templates.length === 0 ? (
        <div className="card"><div className="empty">Sin plantillas. Crea la primera.</div></div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead><tr><th>Procedimiento</th><th>Título</th><th></th></tr></thead>
            <tbody>
              {templates.map((t) => (
                <tr key={t.id}>
                  <td>{t.procedure_display}</td>
                  <td style={{ fontWeight: 600 }}>{t.title}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => setEditing(t)}>Editar</button>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6 }}
                            onClick={() => remove(t)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
