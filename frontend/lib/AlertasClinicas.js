"use client";

/**
 * Alertas clínicas del paciente y sus antecedentes médicos.
 * ────────────────────────────────────────────────────────────────────
 * Las reglas viven en el servidor (`apps/clinical/alertas.py`): aquí
 * solo se enseñan. Cada alerta dice de qué texto salió, porque la regla
 * es una ayuda y quien decide es el profesional.
 *
 * Recepción no ve antecedentes médicos, así que tampoco sus alertas: el
 * servidor responde 403 y aquí no se pinta nada. Cada consulta queda
 * auditada en el servidor, igual que abrir los antecedentes.
 */

import { useCallback, useEffect, useState } from "react";

import { api, readObject } from "./api";

const COLORES = {
  alto: { fondo: "var(--red-soft)", borde: "var(--red)", texto: "var(--red)" },
  medio: { fondo: "var(--amber-soft)", borde: "var(--amber)", texto: "var(--ink)" },
};

/**
 * Choques de una receta con las alertas del paciente. Si la revisión
 * falla se devuelve una lista vacía: no poder avisar no debe impedir
 * guardar la receta.
 */
export async function revisarReceta(patientId, texto) {
  try {
    const resp = await api(`/patients/${patientId}/alertas/revisar/`, {
      method: "POST", body: JSON.stringify({ texto }),
    });
    if (!resp.ok) return [];
    return (await resp.json()).choques || [];
  } catch {
    return [];
  }
}

/** Texto para el diálogo de confirmación al guardar una receta. */
export function textoChoques(choques) {
  return choques.map((c) => `• ${c.titulo}\n   Origen: ${c.fuente}`).join("\n\n")
    + "\n\nEs un aviso automático: revisa la receta. Si lo has valorado, puedes guardarla igualmente.";
}

export default function AlertasPaciente({ patientId }) {
  const [alertas, setAlertas] = useState(null);   // null = sin acceso o cargando
  const [abierto, setAbierto] = useState(false);
  const [editando, setEditando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const resp = await api(`/patients/${patientId}/alertas/`);
      if (!resp.ok) { setAlertas(null); return; }
      setAlertas((await resp.json()).alertas || []);
    } catch { setAlertas(null); }
  }, [patientId]);

  useEffect(() => { cargar(); }, [cargar]);

  if (alertas === null) return null;
  const altas = alertas.filter((a) => a.nivel === "alto").length;

  return (
    <section aria-label="Alertas clínicas" style={{ margin: "10px 0 4px" }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
        {alertas.length === 0 ? (
          <span style={{ fontSize: 13, color: "var(--ink-soft)" }}>Sin alertas en los antecedentes médicos.</span>
        ) : alertas.map((a) => {
          const c = COLORES[a.nivel] || COLORES.medio;
          return (
            <button key={a.clave} type="button" onClick={() => setAbierto(!abierto)}
                    title={`${a.detalle}\nOrigen: ${a.fuente}`}
                    style={{ fontSize: 12.5, fontWeight: 600, padding: "3px 10px", borderRadius: 999,
                             background: c.fondo, color: c.texto, border: `1px solid ${c.borde}`,
                             cursor: "pointer" }}>
              {a.nivel === "alto" ? "⚠ " : ""}{a.titulo}
            </button>
          );
        })}
        {alertas.length > 0 && (
          <button type="button" className="btn btn-ghost" onClick={() => setAbierto(!abierto)}
                  aria-expanded={abierto} style={{ fontSize: 12, padding: "2px 10px" }}>
            {abierto ? "Ocultar detalle" : `Ver detalle${altas ? ` (${altas} importante${altas > 1 ? "s" : ""})` : ""}`}
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={() => setEditando(!editando)}
                style={{ fontSize: 12, padding: "2px 10px" }}>
          {editando ? "Cerrar antecedentes" : "Antecedentes médicos"}
        </button>
      </div>

      {abierto && alertas.length > 0 && (
        <div className="card animate-rise" style={{ marginTop: 8, padding: "10px 14px" }}>
          {alertas.map((a) => (
            <div key={a.clave} style={{ padding: "6px 0", borderBottom: "1px solid var(--line)", fontSize: 13 }}>
              <strong style={{ color: (COLORES[a.nivel] || COLORES.medio).texto }}>{a.titulo}.</strong>{" "}
              {a.detalle}
              <div style={{ fontSize: 12, color: "var(--ink-faint)" }}>Origen: {a.fuente}</div>
            </div>
          ))}
          <p style={{ fontSize: 11.5, color: "var(--ink-faint)", margin: "8px 0 0" }}>
            Avisos automáticos a partir de los antecedentes y del último formulario 033. No sustituyen
            el criterio clínico.
          </p>
        </div>
      )}

      {editando && (
        <EditorAntecedentes patientId={patientId}
                            onGuardado={() => { setEditando(false); cargar(); }} />
      )}
    </section>
  );
}

function EditorAntecedentes({ patientId, onGuardado }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api(`/patients/${patientId}/medical-background/`)
      .then(readObject)
      .then((d) => setDatos({ allergies: d.allergies || "", medications: d.medications || "",
                              conditions: d.conditions || "", is_pregnant: d.is_pregnant }))
      .catch((e) => setError(e.message || "No se pudieron cargar los antecedentes."));
  }, [patientId]);

  async function guardar(e) {
    e.preventDefault();
    setGuardando(true); setError("");
    try {
      await readObject(await api(`/patients/${patientId}/medical-background/`, {
        method: "PUT", body: JSON.stringify(datos),
      }));
      onGuardado();
    } catch (err) { setError(err.message); }
    finally { setGuardando(false); }
  }

  if (!datos) return error ? <div className="error-box" style={{ marginTop: 8 }}>{error}</div> : null;
  const campo = (clave, etiqueta, ayuda) => (
    <div className="field">
      <label>{etiqueta}</label>
      <textarea rows={2} value={datos[clave]} placeholder={ayuda}
                onChange={(e) => setDatos({ ...datos, [clave]: e.target.value })} />
    </div>
  );

  return (
    <form onSubmit={guardar} className="card animate-rise" style={{ marginTop: 8, padding: "12px 14px" }}>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {campo("allergies", "Alergias", "Ej.: penicilina (urticaria). «Niega alergias» si no tiene.")}
        {campo("medications", "Medicación habitual", "Ej.: warfarina 5 mg, metformina 850 mg")}
        {campo("conditions", "Enfermedades y condiciones", "Ej.: hipertensión, prótesis valvular")}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <label style={{ fontSize: 13 }}>
          Embarazo{" "}
          <select value={datos.is_pregnant === null ? "" : String(datos.is_pregnant)}
                  onChange={(e) => setDatos({ ...datos, is_pregnant: e.target.value === "" ? null : e.target.value === "true" })}>
            <option value="">No aplica / sin dato</option>
            <option value="false">No</option>
            <option value="true">Sí</option>
          </select>
        </label>
        <button className="btn btn-primary" disabled={guardando} style={{ marginLeft: "auto" }}>
          {guardando ? "Guardando…" : "Guardar antecedentes"}
        </button>
      </div>
      <p style={{ fontSize: 11.5, color: "var(--ink-faint)", margin: "8px 0 0" }}>
        Una frase que empiece negando («niega…», «sin…», «no toma…») no genera alerta.
        Cada apertura de los antecedentes queda en la auditoría.
      </p>
    </form>
  );
}
