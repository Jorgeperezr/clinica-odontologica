"use client";

/**
 * Sprint 22 — Tabs clínicos de la ficha del paciente:
 * PlanTab (plantillas, progreso, presupuesto automático),
 * DocumentsTab (fotos/documentos por categoría),
 * ConsentsTab (consentimientos con firma táctil).
 */

import { useCallback, useEffect, useState } from "react";
import { api, apiBase } from "./api";
import SignaturePad from "./SignaturePad";
import DocumentPreview from "./DocumentPreview";
import DocumentScanner from "./DocumentScanner";
import { fileSrc } from "./theme";
import { useConfirm } from "./ConfirmDialog";

const money = (v) => `$${Number(v || 0).toFixed(2)}`;

/* ═══════════ Plan de tratamiento ═══════════ */

const ITEM_STATUS = {
  planned: { label: "Planificado", cls: "badge-warn", next: "in_progress", nextLabel: "Iniciar" },
  in_progress: { label: "En progreso", cls: "badge-ok", next: "done", nextLabel: "Marcar realizado" },
  done: { label: "Realizado", cls: "badge-ok", next: null },
};

export function PlanTab({ patientId }) {
  const [confirm, ConfirmUI] = useConfirm();
  const [plans, setPlans] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState("");
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/treatment-plans/`);
      const data = await resp.json();
      setPlans(data.results || data);
    } catch { setError("No se pudieron cargar los planes."); }
  }, [patientId]);

  useEffect(() => {
    load();
    api("/clinical/plan-templates/").then(async (r) => {
      if (r.ok) setTemplates(await r.json());
    }).catch(() => {});
  }, [load]);

  async function applyTemplate() {
    setError(""); setOkMsg("");
    try {
      const resp = await api(`/patients/${patientId}/apply-plan-template/`, {
        method: "POST", body: JSON.stringify({ template_id: templateId }),
      });
      if (!resp.ok) throw new Error(`No se pudo aplicar la plantilla (error ${resp.status}).`);
      setTemplateId("");
      load();
    } catch (err) { setError(err.message); }
  }

  async function setItemStatus(item, status) {
    try {
      const resp = await api(`/treatment-plan-items/${item.id}/`, {
        method: "PATCH", body: JSON.stringify({ status }),
      });
      if (!resp.ok) throw new Error(`No se pudo actualizar (error ${resp.status}).`);
      load();
    } catch (err) { setError(err.message); }
  }

  async function generateBudget(plan) {
    const ok = await confirm({
      title: "Generar presupuesto automático",
      message: "Se creará un presupuesto en Pagos con todos los ítems del plan a sus precios estimados.",
      confirmLabel: "Generar",
    });
    if (!ok) return;
    try {
      const resp = await api(`/treatment-plans/${plan.id}/generate-budget/`, { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.detail || `Error ${resp.status}`);
      setOkMsg(`Presupuesto de ${money(data.total_amount)} creado. Está en Pagos, listo para aprobar y generar cuotas.`);
    } catch (err) { setError(err.message); }
  }

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>✓ {okMsg}</div>}

      {/* Aplicar plantilla */}
      <div className="card" style={{ marginBottom: 18, display: "flex", gap: 10, alignItems: "end", flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0, flex: 1, minWidth: 240 }}>
          <label>Crear plan desde plantilla</label>
          <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
            <option value="">Seleccionar plantilla…</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.items.length} tratamientos · {money(t.total_estimated)})
              </option>
            ))}
          </select>
        </div>
        <button className="btn btn-primary" disabled={!templateId} onClick={applyTemplate}>
          Aplicar al paciente
        </button>
        <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
          Las plantillas se administran en Configuración → Plantillas.
        </span>
      </div>

      {plans.length === 0 ? (
        <div className="card"><div className="empty">Sin planes de tratamiento.</div></div>
      ) : plans.map((plan) => (
        <div key={plan.id} className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
            <div>
              <span className="badge badge-ok">{plan.status_display}</span>
              <span style={{ marginLeft: 10, fontSize: 13, color: "var(--ink-soft)" }}>
                {(plan.created_at || "").slice(0, 10)} · {plan.notes}
              </span>
            </div>
            <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={() => generateBudget(plan)}>
              💰 Generar presupuesto
            </button>
          </div>

          {/* Barra de progreso */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--ink-soft)", marginBottom: 4 }}>
              <span>Progreso del tratamiento</span>
              <span className="tabular">{plan.progress.done}/{plan.progress.total} · {plan.progress.percent}%</span>
            </div>
            <div style={{ height: 8, background: "var(--line)", borderRadius: 99 }}>
              <div style={{ height: 8, width: `${plan.progress.percent}%`,
                            background: "var(--petrol)", borderRadius: 99, transition: "width .3s" }} />
            </div>
          </div>

          <table>
            <thead><tr><th>#</th><th>Tratamiento</th><th>Pieza</th><th>Precio est.</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {plan.items.map((it) => {
                const st = ITEM_STATUS[it.status] || ITEM_STATUS.planned;
                return (
                  <tr key={it.id}>
                    <td className="tabular">{it.order}</td>
                    <td style={{ fontWeight: 600 }}>{it.treatment_name}</td>
                    <td className="tabular">{it.tooth_fdi_code || "—"}</td>
                    <td className="tabular">{money(it.estimated_price)}</td>
                    <td><span className={`badge ${st.cls}`}>{st.label}</span></td>
                    <td style={{ textAlign: "right" }}>
                      {st.next && (
                        <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                                onClick={() => setItemStatus(it, st.next)}>{st.nextLabel}</button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

/* ═══════════ Documentos y fotos ═══════════ */

const DOC_CATEGORIES = {
  radiograph: "Radiografía", photo: "Foto clínica", exam: "Examen / laboratorio",
  report: "Informe", identification: "Identificación", medical_order: "Orden médica",
  referral: "Referencia", other: "Otro",
};

export function DocumentsTab({ patientId }) {
  const { confirm, ConfirmUI } = useConfirm();
  const [docs, setDocs] = useState([]);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [sortBy, setSortBy] = useState("date_desc");
  const [view, setView] = useState("grid");     // grid | list
  const [preview, setPreview] = useState(null);  // documento en vista previa
  const [scanning, setScanning] = useState(false);
  const [form, setForm] = useState({ doc_type: "photo", description: "" });
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/documents/`);
      const data = await resp.json();
      setDocs(data.results || data);
    } catch { setError("No se pudieron cargar los documentos."); }
  }, [patientId]);

  useEffect(() => { load(); }, [load]);

  async function upload(e) {
    e.preventDefault();
    if (!file) { setError("Selecciona un archivo."); return; }
    setError("");
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("doc_type", form.doc_type);
      fd.append("description", form.description);
      fd.append("file", file);
      // FormData: sin Content-Type manual (el navegador pone el boundary)
      const token = localStorage.getItem("access");
      const resp = await fetch(`${apiBase()}/api/v1/patients/${patientId}/documents/`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!resp.ok) throw new Error(`No se pudo subir (error ${resp.status}).`);
      setForm({ doc_type: "photo", description: "" });
      setFile(null);
      e.target.reset?.();
      load();
    } catch (err) { setError(err.message); }
    finally { setUploading(false); }
  }

  async function removeDoc(d) {
    const ok = await confirm({
      title: "Eliminar documento",
      message: `Se eliminará "${d.description || d.file_name || "el documento"}" del expediente.\nEl registro se conserva para trazabilidad clínica.`,
      confirmLabel: "Eliminar",
    });
    if (!ok) return;
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/documents/${d.id}/`, { method: "DELETE" });
      if (!resp.ok && resp.status !== 204) {
        throw new Error(resp.status === 403
          ? "No tienes permiso para eliminar documentos."
          : `No se pudo eliminar (error ${resp.status}).`);
      }
      if (preview?.id === d.id) setPreview(null);
      load();
    } catch (err) { setError(err.message); }
  }

  function fmtSize(bytes) {
    if (!bytes) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }
  const isImage = (d) => /\.(png|jpe?g|gif|webp)$/i.test(d.file_name || d.file_url || "");

  // Filtrado + búsqueda + orden (en el cliente)
  let visible = docs.slice();
  if (filter) visible = visible.filter((d) => d.doc_type === filter);
  if (search.trim()) {
    const q = search.trim().toLowerCase();
    visible = visible.filter((d) =>
      (d.description || "").toLowerCase().includes(q) ||
      (d.file_name || "").toLowerCase().includes(q));
  }
  if (dateFrom) visible = visible.filter((d) => (d.uploaded_at || "") >= dateFrom);
  visible.sort((a, b) => {
    if (sortBy === "date_asc") return (a.uploaded_at || "").localeCompare(b.uploaded_at || "");
    if (sortBy === "date_desc") return (b.uploaded_at || "").localeCompare(a.uploaded_at || "");
    if (sortBy === "name_asc") return (a.description || a.file_name || "").localeCompare(b.description || b.file_name || "");
    return 0;
  });

  return (
    <div>
      <ConfirmUI />
      {error && <div className="error-box">{error}</div>}
      {preview && (
        <DocumentPreview doc={preview} patientId={patientId} onClose={() => setPreview(null)}
                         onDelete={() => removeDoc(preview)} />
      )}
      {scanning && (
        <DocumentScanner patientId={patientId} docType={form.doc_type}
                         onClose={() => setScanning(false)}
                         onDone={() => { setScanning(false); load(); }} />
      )}

      <form onSubmit={upload} className="card" style={{ marginBottom: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>Subir documento o foto</h3>
          <button type="button" className="btn btn-ghost" style={{ fontSize: 13 }}
                  onClick={() => setScanning(true)}>📷 Escanear documento</button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr 2fr auto", gap: "0 12px", alignItems: "end" }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Categoría</label>
            <select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })}>
              {Object.entries(DOC_CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Descripción *</label>
            <input required value={form.description}
                   onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Archivo *</label>
            <input type="file" required accept="image/*,.pdf,.doc,.docx"
                   onChange={(e) => setFile(e.target.files[0])} /></div>
          <button className="btn btn-primary" disabled={uploading}>
            {uploading ? "Subiendo…" : "Subir"}
          </button>
        </div>
      </form>

      {/* Barra de herramientas: búsqueda, filtros, orden, vista */}
      <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "end" }}>
        <div className="field" style={{ marginBottom: 0, flex: "1 1 200px" }}>
          <label>Buscar por nombre</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Nombre o descripción…" />
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Desde fecha</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Ordenar</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="date_desc">Fecha (recientes primero)</option>
            <option value="date_asc">Fecha (antiguos primero)</option>
            <option value="name_asc">Nombre (A-Z)</option>
          </select>
        </div>
        <div style={{ display: "flex", gap: 4, paddingBottom: 2 }}>
          <button className={`btn ${view === "grid" ? "btn-primary" : "btn-ghost"}`}
                  style={{ fontSize: 12, padding: "7px 12px" }} onClick={() => setView("grid")}>▦ Cuadrícula</button>
          <button className={`btn ${view === "list" ? "btn-primary" : "btn-ghost"}`}
                  style={{ fontSize: 12, padding: "7px 12px" }} onClick={() => setView("list")}>☰ Lista</button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        <button className={`btn ${filter === "" ? "btn-primary" : "btn-ghost"}`}
                style={{ fontSize: 12, padding: "5px 12px" }} onClick={() => setFilter("")}>Todos</button>
        {Object.entries(DOC_CATEGORIES).map(([k, v]) => (
          docs.some((d) => d.doc_type === k) && (
            <button key={k} className={`btn ${filter === k ? "btn-primary" : "btn-ghost"}`}
                    style={{ fontSize: 12, padding: "5px 12px" }} onClick={() => setFilter(k)}>{v}</button>
          )
        ))}
      </div>

      {visible.length === 0 ? (
        <div className="card"><div className="empty">Sin documentos que coincidan.</div></div>
      ) : view === "grid" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 14 }}>
          {visible.map((d) => (
            <div key={d.id} className="card" style={{ padding: 12, position: "relative", border: "1px solid var(--line)" }}>
              <button onClick={(e) => { e.stopPropagation(); removeDoc(d); }}
                      title="Eliminar documento"
                      style={{ position: "absolute", top: 8, right: 8, zIndex: 2,
                               background: "var(--card)", border: "1px solid var(--line)",
                               borderRadius: 6, cursor: "pointer", padding: "2px 7px",
                               fontSize: 13, lineHeight: 1.2, color: "var(--red)" }}>✕</button>
              <button onClick={() => setPreview(d)}
                      style={{ all: "unset", cursor: "pointer", display: "block", width: "100%" }}>
              {isImage(d) ? (
                <img src={fileSrc(d.file_url)} alt={d.description}
                     style={{ width: "100%", height: 130, objectFit: "cover", borderRadius: 8, marginBottom: 8 }} />
              ) : (
                <div style={{ height: 130, display: "flex", alignItems: "center", justifyContent: "center",
                              background: "var(--petrol-soft)", borderRadius: 8, marginBottom: 8, fontSize: 34 }}>📄</div>
              )}
              <div style={{ fontWeight: 600, fontSize: 13, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {d.description || d.file_name || "Documento"}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>
                {d.doc_type_display || DOC_CATEGORIES[d.doc_type] || d.doc_type} · {(d.uploaded_at || "").slice(0, 10)}
              </div>
              <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>
                {fmtSize(d.file_size)} · {d.uploaded_by_name || "—"}
              </div>
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead><tr><th>Nombre</th><th>Categoría</th><th>Tamaño</th><th>Cargado por</th><th>Fecha</th><th></th></tr></thead>
            <tbody>
              {visible.map((d) => (
                <tr key={d.id}>
                  <td style={{ fontWeight: 600 }}>{d.description || d.file_name || "Documento"}</td>
                  <td>{d.doc_type_display || DOC_CATEGORIES[d.doc_type] || d.doc_type}</td>
                  <td className="tabular">{fmtSize(d.file_size)}</td>
                  <td>{d.uploaded_by_name || "—"}</td>
                  <td className="tabular">{(d.uploaded_at || "").slice(0, 10)}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => setPreview(d)}>Ver</button>
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12,
                                                               marginLeft: 6, color: "var(--red)" }}
                            onClick={() => removeDoc(d)}>Eliminar</button>
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

/* ═══════════ Consentimientos con firma táctil ═══════════ */

export function ConsentsTab({ patientId }) {

  async function openConsentPdf(consent) {
    try {
      const resp = await api(`/consents/${consent.id}/pdf/`);
      if (!resp.ok) throw new Error(`No se pudo generar el PDF (error ${resp.status}).`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 15000);
    } catch (err) { console.error(err); }
  }
  const [consents, setConsents] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [form, setForm] = useState({ title: "", body_text: "" });
  const [signing, setSigning] = useState(null);   // consentimiento a firmar
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/consents/`);
      const data = await resp.json();
      setConsents(data.results || data);
    } catch { setError("No se pudieron cargar los consentimientos."); }
  }, [patientId]);

  const loadTemplates = useCallback(async () => {
    try {
      const resp = await api("/consent-templates/");
      const data = await resp.json();
      setTemplates(data.results || data);
    } catch { /* opcional */ }
  }, []);

  useEffect(() => { load(); loadTemplates(); }, [load, loadTemplates]);

  function applyTemplate(id) {
    const t = templates.find((x) => x.id === id);
    if (!t) return;
    // Compone el cuerpo desde las secciones de la plantilla (editable después)
    const parts = [];
    if (t.procedure_text) parts.push(`PROCEDIMIENTO:\n${t.procedure_text}`);
    if (t.benefits) parts.push(`BENEFICIOS:\n${t.benefits}`);
    if (t.risks) parts.push(`RIESGOS Y COMPLICACIONES:\n${t.risks}`);
    if (t.alternatives) parts.push(`ALTERNATIVAS:\n${t.alternatives}`);
    if (t.body_text) parts.push(t.body_text);
    setForm({ title: t.title, body_text: parts.join("\n\n") });
  }

  async function create(e) {
    e.preventDefault();
    setError("");
    try {
      const resp = await api(`/patients/${patientId}/consents/`, {
        method: "POST", body: JSON.stringify(form),
      });
      if (!resp.ok) throw new Error(`No se pudo crear (error ${resp.status}).`);
      setForm({ title: "", body_text: "" });
      load();
    } catch (err) { setError(err.message); }
  }

  async function submitSignature(dataUrl) {
    try {
      const resp = await api(`/consents/${signing.id}/sign/`, {
        method: "POST",
        body: JSON.stringify({ signature_image_base64: dataUrl }),
      });
      if (!resp.ok) throw new Error(`No se pudo registrar la firma (error ${resp.status}).`);
      setSigning(null);
      load();
    } catch (err) { setError(err.message); setSigning(null); }
  }

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      {signing && (
        <SignaturePad onConfirm={submitSignature} onCancel={() => setSigning(null)} />
      )}

      <form onSubmit={create} className="card" style={{ marginBottom: 18 }}>
        <h3 style={{ marginBottom: 12 }}>Nuevo consentimiento informado</h3>
        {templates.length > 0 && (
          <div className="field">
            <label>Partir de una plantilla (opcional)</label>
            <select defaultValue="" onChange={(e) => { applyTemplate(e.target.value); e.target.value = ""; }}>
              <option value="">— Seleccionar plantilla —</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.procedure_display} · {t.title}</option>
              ))}
            </select>
            <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 4 }}>
              La plantilla rellena el texto; puedes editarlo antes de guardar. Las plantillas se administran en Configuración.
            </p>
          </div>
        )}
        <div className="field">
          <label>Título *</label>
          <input required placeholder="Ej: Consentimiento para extracción de pieza 16"
                 value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </div>
        <div className="field">
          <label>Texto del consentimiento *</label>
          <textarea rows={5} required
                    placeholder="Descripción del procedimiento, riesgos, alternativas y declaración de aceptación…"
                    value={form.body_text} onChange={(e) => setForm({ ...form, body_text: e.target.value })} />
        </div>
        <button className="btn btn-primary">Crear (queda pendiente de firma)</button>
      </form>

      <div className="card" style={{ padding: 0 }}>
        {consents.length === 0 ? (
          <div className="empty">Sin consentimientos.</div>
        ) : (
          <table>
            <thead><tr><th>Título</th><th>Creado</th><th>Estado</th><th></th></tr></thead>
            <tbody>
              {consents.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 600 }}>{c.title}</td>
                  <td className="tabular">{(c.created_at || "").slice(0, 10)}</td>
                  <td>{
                    c.status === "signed" || c.is_signed
                      ? <span className="badge badge-ok">Firmado {(c.signed_at || "").slice(0, 10)}</span>
                      : c.status === "void"
                        ? <span className="badge badge-danger">Anulado</span>
                        : c.status === "draft"
                          ? <span className="badge" style={{ background: "var(--line)", color: "var(--ink-soft)" }}>Borrador</span>
                          : <span className="badge badge-warn">Pendiente de firma</span>
                  }</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <span style={{ display: "inline-flex", gap: 6 }}>
                      <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }}
                              onClick={() => openConsentPdf(c)}
                              title="Ver, descargar o imprimir el consentimiento">
                        Generar PDF
                      </button>
                      {!c.is_signed && (
                        <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                                onClick={() => setSigning(c)}>Firmar ahora</button>
                      )}
                    </span>
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
