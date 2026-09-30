"use client";

/**
 * Configuración → Copia de seguridad (Sprint 65).
 * ────────────────────────────────────────────────────────────────────
 * La administradora de la clínica genera aquí un archivo cifrado con
 * los datos de SU clínica y, desde la misma pantalla, lo vuelve a abrir
 * escribiendo la frase con la que lo cifró.
 *
 * La frase no viaja a ningún almacén ni queda en la auditoría: el
 * servidor la usa para derivar la clave y la olvida. Por eso la
 * pantalla insiste en guardarla aparte — sin ella el archivo es
 * irrecuperable, que es exactamente lo que se le pide al cifrado.
 *
 * Abrir una copia NO restaura nada: muestra lo que contiene y permite
 * descargarlo en claro. Reemplazar la base de datos es una operación
 * destructiva que se hace desde el servidor y no debe estar a un clic.
 *
 * Lo que se descarga es un .zip con la copia y lo necesario para abrirla
 * SIN la plataforma: instrucciones, una herramienta para el navegador
 * que funciona sin internet y otra para la terminal (ver
 * django-api/apps/common/paquete_respaldo.py).
 *
 * `alcance="profesional"`: la misma pantalla para un doctor o auxiliar,
 * con la copia de SUS pacientes (página «Mi respaldo»).
 */

import { useState } from "react";

import { api } from "./api";

const MIN_PASSPHRASE = 12;

const nf = new Intl.NumberFormat("es-EC");

/** Nombres legibles de las tablas, para no enseñar `patients.Patient`. */
const MODEL_LABELS = {
  "accounts.AuditLog": "Registros de auditoría",
  "accounts.User": "Usuarios del personal",
  "agenda.Appointment": "Citas",
  "agenda.Doctor": "Doctores",
  "billing.Budget": "Presupuestos",
  "billing.BudgetItem": "Ítems de presupuesto",
  "billing.DoctorFee": "Honorarios",
  "billing.Installment": "Cuotas",
  "billing.Payment": "Pagos",
  "billing.PaymentPlan": "Planes de pago",
  "clinical.ClinicalRecord": "Fichas clínicas",
  "clinical.ConsentAuditLog": "Auditoría de consentimientos",
  "clinical.ConsentTemplate": "Plantillas de consentimiento",
  "clinical.Diagnosis": "Diagnósticos",
  "clinical.Evolution": "Evoluciones",
  "clinical.ExamRequest": "Solicitudes de examen",
  "clinical.Form033Record": "Formularios MSP 033",
  "clinical.InformedConsent": "Consentimientos informados",
  "clinical.OdontogramState": "Estados del odontograma",
  "clinical.PeriodontalExam": "Exámenes periodontales",
  "clinical.PeriodontalTooth": "Piezas del periodontograma",
  "clinical.RadiographPhoto": "Radiografías y fotos",
  "clinical.ToothRecord": "Registros por pieza",
  "clinical.TreatmentPlan": "Planes de tratamiento",
  "clinical.TreatmentPlanItem": "Ítems de plan",
  "clinical.TreatmentPlanTemplate": "Plantillas de plan",
  "clinical.TreatmentPlanTemplateItem": "Ítems de plantilla",
  "configuration.Agreement": "Convenios",
  "configuration.ClinicBranding": "Personalización",
  "configuration.DocumentAppearance": "Apariencia de documentos",
  "configuration.SystemParameter": "Parámetros del sistema",
  "configuration.Tariff": "Tarifarios",
  "configuration.Treatment": "Tratamientos",
  "configuration.TreatmentInventoryItem": "Insumos por tratamiento",
  "inventory.Batch": "Lotes",
  "inventory.InventoryMovement": "Movimientos de inventario",
  "inventory.Product": "Productos",
  "patients.MedicalBackground": "Antecedentes médicos",
  "patients.Patient": "Pacientes",
  "patients.PatientDocument": "Documentos de pacientes",
  "specialties.Specialty": "Especialidades",
  "specialties.SpecialtyForm": "Formularios por especialidad",
  "whatsapp.WhatsAppMessageLog": "Mensajes de WhatsApp",
  "whatsapp.WhatsAppOptIn": "Consentimientos de WhatsApp",
  "whatsapp.WhatsAppTemplate": "Plantillas de WhatsApp",
  "whatsapp.ConfiguracionWhatsApp": "Configuración de WhatsApp",
  "app_paciente.SolicitudCita": "Solicitudes de cita (app)",
  "app_paciente.MensajeConsultorio": "Mensajes de la app",
  "logros.Logro": "Logros",
  "logros.LogroDePaciente": "Logros concedidos",
};

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}`;
}

export default function ClinicBackup({ alcance = "clinica" }) {
  const propia = alcance === "profesional";
  return (
    <div style={{ display: "grid", gap: 18, maxWidth: 860 }}>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
        {propia ? (
          <>Descarga una copia cifrada con la información de <strong>los pacientes que atiendes</strong>
          —sus datos, su historia clínica completa, odontogramas, evoluciones y recetas— y tu
          agenda. No lleva cobros, inventario ni pacientes de otros profesionales. Solo tú puedes
          abrirla en el panel, además de la administración de la clínica.</>
        ) : (
          <>Descarga una copia cifrada con los datos de esta clínica —pacientes, historias,
          citas, pagos e inventario— y ábrela cuando la necesites escribiendo la frase con
          la que la cifraste. Cada doctor o auxiliar puede sacar, desde «Mi respaldo», la de
          sus propios pacientes; se le quita desmarcando su función en Usuarios.</>
        )}
      </p>
      <CreateCard propia={propia} />
      <ComoAbrir />
      <OpenCard propia={propia} />
    </div>
  );
}

/* ── Cómo abrirla fuera de la plataforma ─────────────────────────────── */
function ComoAbrir() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function herramientas() {
    setBusy(true); setError("");
    try {
      const resp = await api("/config/backup/herramientas/");
      if (!resp.ok) throw new Error(`No se pudieron descargar (error ${resp.status}).`);
      download(await resp.blob(), "como-descifrar-la-copia.zip");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const paso = { margin: "0 0 6px", fontSize: 13.5 };
  return (
    <div className="card">
      <h3 style={{ marginBottom: 6 }}>Cómo abrir la copia</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 0 }}>
        La descarga es un <strong>.zip</strong> que trae la copia cifrada (<code>.clinicabk</code>) y
        todo lo necesario para abrirla, también <strong>sin la plataforma</strong>. Las mismas
        instrucciones van dentro, en <code>COMO-DESCIFRAR.txt</code>.
      </p>
      {error && <div className="error-box">{error}</div>}
      <ol style={{ paddingLeft: 20, margin: "0 0 12px" }}>
        <li style={paso}>
          <strong>Aquí mismo</strong>, en «Abrir una copia»: elige el .zip o el .clinicabk y escribe
          la frase.
        </li>
        <li style={paso}>
          <strong>Sin la plataforma y sin internet:</strong> descomprime el .zip y abre{" "}
          <code>descifrar.html</code> con Chrome, Edge, Firefox o Safari. Todo ocurre en tu equipo:
          el archivo y la frase no se envían a ningún sitio. Enseña cada tabla y la descarga en
          CSV (Excel, Numbers, LibreOffice) o en JSON.
        </li>
        <li style={paso}>
          <strong>Desde la terminal</strong> (personal técnico): <code>descifrar.py</code>, con Python
          3.8+ y la biblioteca <code>cryptography</code>.
        </li>
        <li style={paso}>
          <strong>Con cualquier otra herramienta:</strong> el formato es abierto (AES-256-GCM con
          clave PBKDF2-SHA256) y está descrito paso a paso en <code>COMO-DESCIFRAR.txt</code>.
        </li>
      </ol>
      <button className="btn btn-ghost" disabled={busy} onClick={herramientas}>
        {busy ? "Descargando…" : "Descargar solo las herramientas e instrucciones"}
      </button>
      <span style={{ fontSize: 12, color: "var(--ink-faint)", marginLeft: 10 }}>
        Para copias antiguas o si perdiste el .zip y conservas el .clinicabk.
      </span>
    </div>
  );
}

/* ── Generar ─────────────────────────────────────────────────────────── */
function CreateCard({ propia }) {
  const [phrase, setPhrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const short = phrase.length > 0 && phrase.length < MIN_PASSPHRASE;
  const mismatch = confirm.length > 0 && confirm !== phrase;
  const ready = phrase.length >= MIN_PASSPHRASE && confirm === phrase && understood && !busy;

  async function create() {
    setBusy(true); setError(""); setOkMsg("");
    try {
      const resp = await api("/config/backup/", {
        method: "POST",
        body: JSON.stringify({ passphrase: phrase, passphrase_confirm: confirm }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data?.error?.message || data?.detail || `Error ${resp.status}`);
      }
      const disposition = resp.headers.get("Content-Disposition") || "";
      const named = /filename="([^"]+)"/.exec(disposition);
      const records = resp.headers.get("X-Backup-Records");
      download(await resp.blob(), named ? named[1] : `respaldo-${stamp()}.zip`);
      setOkMsg(`Copia generada${records ? ` con ${nf.format(Number(records))} registros` : ""}. `
        + "El .zip trae también las instrucciones y las herramientas para abrirla. "
        + "Guárdalo fuera de este equipo y la frase en otro sitio.");
      setPhrase(""); setConfirm(""); setUnderstood(false);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="card">
      <h3 style={{ marginBottom: 6 }}>{propia ? "Generar la copia de mis pacientes" : "Generar una copia cifrada"}</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 0, marginBottom: 12 }}>
        El archivo se cifra con AES-256 a partir de la frase que escribas. Los archivos
        adjuntos (radiografías, documentos escaneados) no van dentro: la copia guarda su
        referencia, no su contenido.
      </p>

      <div style={{ padding: "10px 14px", borderRadius: 10, background: "var(--petrol-soft)",
                    fontSize: 13, marginBottom: 14 }}>
        <strong>Sin la frase no hay forma de abrir el archivo.</strong> No se guarda en
        ninguna parte del sistema, ni siquiera cifrada: escríbela en un gestor de
        contraseñas o guárdala en un lugar seguro y distinto de donde guardes la copia.
      </div>

      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="success-box">✓ {okMsg}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Frase de cifrado (mínimo {MIN_PASSPHRASE} caracteres)</label>
          <input type="password" value={phrase} autoComplete="new-password"
                 onChange={(e) => setPhrase(e.target.value)} />
          {short && (
            <div style={{ fontSize: 12, color: "var(--red, #b91c1c)" }}>
              Te faltan {MIN_PASSPHRASE - phrase.length} caracteres.
            </div>
          )}
        </div>
        <div className="field" style={{ marginBottom: 0 }}>
          <label>Repite la frase</label>
          <input type="password" value={confirm} autoComplete="new-password"
                 onChange={(e) => setConfirm(e.target.value)} />
          {mismatch && (
            <div style={{ fontSize: 12, color: "var(--red, #b91c1c)" }}>No coincide.</div>
          )}
        </div>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13,
                      margin: "14px 0", cursor: "pointer" }}>
        <input type="checkbox" checked={understood}
               onChange={(e) => setUnderstood(e.target.checked)} />
        He guardado la frase en un lugar seguro.
      </label>

      <button className="btn btn-primary" disabled={!ready} onClick={create}>
        {busy ? "Generando…" : "Generar y descargar"}
      </button>
    </div>
  );
}

/* ── Abrir ───────────────────────────────────────────────────────────── */
function OpenCard({ propia }) {
  const [file, setFile] = useState(null);
  const [phrase, setPhrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);

  async function open() {
    setBusy(true); setError(""); setPayload(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("passphrase", phrase);
      const resp = await api("/config/backup/decrypt/", { method: "POST", body: fd });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data?.error?.message || data?.detail || `Error ${resp.status}`);
      setPayload(data);
      setPhrase("");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const manifest = payload?.manifest;
  const counts = manifest ? Object.entries(manifest.counts || {}) : [];

  return (
    <div className="card">
      <h3 style={{ marginBottom: 6 }}>Abrir una copia</h3>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", marginTop: 0, marginBottom: 12 }}>
        Descifra un archivo para consultar su contenido o guardarlo en claro. No modifica
        los datos actuales de la clínica.
        {propia && " Aquí solo se abren las copias que generaste tú."}
      </p>

      {error && <div className="error-box">{error}</div>}

      <div style={{ display: "flex", gap: 14, alignItems: "end", flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0, flex: "1 1 240px" }}>
          <label>Archivo de la copia (.zip o .clinicabk)</label>
          <input type="file" accept=".clinicabk,.zip,application/octet-stream,application/zip"
                 onChange={(e) => { setFile(e.target.files?.[0] || null); setPayload(null); }} />
        </div>
        <div className="field" style={{ marginBottom: 0, flex: "1 1 220px" }}>
          <label>Frase de cifrado</label>
          <input type="password" value={phrase} autoComplete="off"
                 onChange={(e) => setPhrase(e.target.value)} />
        </div>
        <button className="btn btn-primary" disabled={!file || !phrase || busy} onClick={open}>
          {busy ? "Descifrando…" : "Descifrar"}
        </button>
      </div>

      {manifest && (
        <div style={{ marginTop: 18 }}>
          <div className="success-box">
            ✓ Copia de <strong>{manifest.tenant?.name}</strong> del{" "}
            {new Date(manifest.generated_at).toLocaleString("es-EC")}
            {manifest.generated_by?.email ? `, generada por ${manifest.generated_by.email}` : ""}.
            {manifest.alcance?.tipo === "profesional" && (
              <> Contiene los {nf.format(manifest.alcance.pacientes || 0)} pacientes de{" "}
                {manifest.alcance.full_name || manifest.alcance.email}.</>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                        margin: "12px 0 8px", flexWrap: "wrap", gap: 10 }}>
            <strong style={{ fontSize: 14 }}>
              {nf.format(manifest.total_records || 0)} registros en {counts.length} tablas
            </strong>
            <button className="btn btn-ghost"
                    onClick={() => download(
                      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
                      `respaldo-descifrado-${stamp()}.json`)}>
              Descargar en JSON
            </button>
          </div>

          <div className="card" style={{ padding: 0, maxHeight: 340, overflow: "auto" }}>
            <table>
              <thead><tr><th>Contenido</th><th style={{ textAlign: "right" }}>Registros</th></tr></thead>
              <tbody>
                {counts.sort((a, b) => b[1] - a[1]).map(([model, n]) => (
                  <tr key={model}>
                    <td>{MODEL_LABELS[model] || model}</td>
                    <td className="tabular" style={{ textAlign: "right" }}>{nf.format(n)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 10 }}>
            El archivo JSON que descargas está <strong>sin cifrar</strong>: contiene datos de
            salud. Bórralo del equipo cuando termines de usarlo.
          </p>
        </div>
      )}
    </div>
  );
}
