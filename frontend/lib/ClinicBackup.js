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

export default function ClinicBackup() {
  return (
    <div style={{ display: "grid", gap: 18, maxWidth: 860 }}>
      <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
        Descarga una copia cifrada con los datos de esta clínica —pacientes, historias,
        citas, pagos e inventario— y ábrela cuando la necesites escribiendo la frase con
        la que la cifraste. Solo la administración de la clínica puede hacerlo.
      </p>
      <CreateCard />
      <OpenCard />
    </div>
  );
}

/* ── Generar ─────────────────────────────────────────────────────────── */
function CreateCard() {
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
      download(await resp.blob(), named ? named[1] : `respaldo-${stamp()}.clinicabk`);
      setOkMsg(records
        ? `Copia generada con ${nf.format(Number(records))} registros. Guárdala fuera de este equipo.`
        : "Copia generada. Guárdala fuera de este equipo.");
      setPhrase(""); setConfirm(""); setUnderstood(false);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="card">
      <h3 style={{ marginBottom: 6 }}>Generar una copia cifrada</h3>
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
function OpenCard() {
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
      </p>

      {error && <div className="error-box">{error}</div>}

      <div style={{ display: "flex", gap: 14, alignItems: "end", flexWrap: "wrap" }}>
        <div className="field" style={{ marginBottom: 0, flex: "1 1 240px" }}>
          <label>Archivo de la copia</label>
          <input type="file" accept=".clinicabk,application/octet-stream"
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
