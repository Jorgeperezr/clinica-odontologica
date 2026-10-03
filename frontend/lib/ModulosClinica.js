"use client";

/**
 * Configuración → Módulos: qué usa esta clínica.
 *
 * La plataforma decide qué tiene contratado cada clínica; aquí la
 * administración decide, dentro de eso, qué quiere usar. Apagar el
 * odontograma 3D o las rachas y logros los quita del panel, de la ficha
 * y de la app del paciente para todo el equipo. No borra nada: al
 * encenderlo de nuevo, todo sigue ahí.
 */

import { useEffect, useState } from "react";

import { api, currentUser } from "./api";

/** El perfil en caché es de donde el menú y la ficha leen los módulos. */
function recordar(modulos) {
  try {
    const u = currentUser();
    if (!u) return;
    const funcionalidades = Object.fromEntries(modulos.map((m) => [m.clave, m.activo]));
    localStorage.setItem("user", JSON.stringify({ ...u, funcionalidades }));
    window.dispatchEvent(new Event("perfil-actualizado"));
  } catch { /* modo privado: se verá en el próximo inicio de sesión */ }
}

export default function ModulosClinica() {
  const [modulos, setModulos] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(null);

  useEffect(() => {
    api("/config/modulos/").then(async (r) => {
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || "No se pudieron cargar los módulos.");
      setModulos(d);
    }).catch((e) => setError(e.message));
  }, []);

  async function cambiar(m) {
    setGuardando(m.clave); setError("");
    try {
      const r = await api("/config/modulos/", {
        method: "PATCH", body: JSON.stringify({ [m.clave]: !m.activo }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `No se pudo guardar (error ${r.status}).`);
      setModulos(d);
      recordar(d);
    } catch (e) { setError(e.message); }
    finally { setGuardando(null); }
  }

  if (!modulos) return error ? <div className="error-box">{error}</div> : <div className="empty">Cargando…</div>;
  const contratados = modulos.filter((m) => m.contratado);
  const otros = modulos.filter((m) => !m.contratado);

  return (
    <div style={{ maxWidth: 820 }}>
      <p style={{ fontSize: 13.5, color: "var(--ink-soft)", margin: "0 0 14px" }}>
        Enciende o apaga lo que tu clínica usa. Se aplica a todo el equipo y a la app de los
        pacientes. Apagar un módulo no borra sus datos: si lo vuelves a encender, todo sigue ahí.
      </p>
      {error && <div className="error-box">{error}</div>}
      <div className="card" style={{ padding: 0 }}>
        {contratados.map((m, i) => (
          <label key={m.clave}
                 style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 18px",
                          borderTop: i ? "1px solid var(--line)" : "none", cursor: "pointer" }}>
            <span style={{ flex: 1 }}>
              <strong style={{ fontSize: 14.5 }}>{m.nombre}</strong>
              <span style={{ display: "block", fontSize: 12.5, color: "var(--ink-soft)" }}>{m.descripcion}</span>
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, minWidth: 64, textAlign: "right",
                           color: m.activo ? "var(--green)" : "var(--ink-faint)" }}>
              {guardando === m.clave ? "Guardando…" : m.activo ? "Encendido" : "Apagado"}
            </span>
            <Interruptor activo={m.activo} ocupado={guardando === m.clave} onClick={() => cambiar(m)}
                         etiqueta={m.nombre} />
          </label>
        ))}
      </div>
      {otros.length > 0 && (
        <p style={{ fontSize: 12.5, color: "var(--ink-faint)", marginTop: 12 }}>
          No incluidos en tu plan: {otros.map((m) => m.nombre).join(", ")}. Para añadirlos, habla con
          el administrador de la plataforma.
        </p>
      )}
    </div>
  );
}

/** Interruptor accesible: un botón con role="switch". */
export function Interruptor({ activo, ocupado, onClick, etiqueta }) {
  return (
    <button type="button" role="switch" aria-checked={activo} aria-label={etiqueta}
            disabled={ocupado} onClick={(e) => { e.preventDefault(); onClick(); }}
            style={{ width: 44, height: 26, borderRadius: 999, border: "none", padding: 3,
                     background: activo ? "var(--petrol)" : "var(--line-strong)",
                     display: "flex", justifyContent: activo ? "flex-end" : "flex-start",
                     transition: "background var(--dur) var(--ease)", flexShrink: 0 }}>
      <span style={{ width: 20, height: 20, borderRadius: "50%", background: "#fff",
                     boxShadow: "0 1px 3px rgba(0,0,0,.25)" }} />
    </button>
  );
}
