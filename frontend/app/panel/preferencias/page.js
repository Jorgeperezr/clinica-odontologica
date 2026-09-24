"use client";

/**
 * Mis preferencias: lo que cada profesional decide para sí mismo.
 *
 * Por ahora, usar o no el odontograma 3D. Lo que la clínica tiene
 * contratado lo decide el dueño de la plataforma; aquí solo se elige,
 * dentro de eso, lo que cada cual quiere ver. El odontograma clásico no
 * se apaga nunca: es el del formulario oficial.
 */

import { useEffect, useState } from "react";
import { api, currentUser } from "../../../lib/api";

const OPCIONES = [
  {
    clave: "odontograma_3d",
    titulo: "Odontograma 3D",
    texto: "Muestra el modelo tridimensional en la ficha de cada paciente, junto al clásico, "
      + "el anatómico y el periodontograma. Apágalo si trabajas mejor sin él o si tu equipo "
      + "lo mueve con dificultad: los datos clínicos son los mismos en todos los modelos.",
    sinContrato: "Tu clínica no tiene contratado el odontograma 3D. Pídeselo al administrador "
      + "de la plataforma si lo necesitas.",
  },
];

/** Guarda las preferencias en el perfil en caché, que es de donde las lee la ficha. */
function recordar(preferencias) {
  try {
    const u = currentUser();
    if (u) localStorage.setItem("user", JSON.stringify({ ...u, preferencias }));
  } catch { /* modo privado: se aplicará en el próximo inicio de sesión */ }
}

export default function PreferenciasPage() {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(null);

  useEffect(() => {
    api("/auth/me/preferencias/").then(async (r) => {
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || "No se pudieron cargar tus preferencias.");
      setDatos(d);
      recordar(d.preferencias);
    }).catch((e) => setError(e.message));
  }, []);

  async function cambiar(clave, valor) {
    setError(""); setGuardando(clave);
    try {
      const r = await api("/auth/me/preferencias/", {
        method: "PATCH", body: JSON.stringify({ [clave]: valor }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) throw new Error(d?.detail || `No se pudo guardar (error ${r.status}).`);
      setDatos(d);
      recordar(d.preferencias);
    } catch (e) {
      setError(e.message);
    } finally {
      setGuardando(null);
    }
  }

  return (
    <div style={{ maxWidth: 680 }}>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Mis preferencias</h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 18, fontSize: 14 }}>
        Solo te afectan a ti: el resto del equipo sigue viendo el panel como lo tenga configurado.
      </p>

      {error && <div className="error-box">{error}</div>}
      {!datos && !error && <div className="skeleton" style={{ height: 96 }} />}

      {datos && OPCIONES.map((o) => {
        const disponible = datos.disponibles?.[o.clave] !== false;
        const activa = Boolean(datos.preferencias?.[o.clave]);
        return (
          <div key={o.clave} className="card" style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
            <div style={{ flex: 1 }}>
              <h3 style={{ margin: "0 0 4px", fontSize: 16 }}>{o.titulo}</h3>
              <p style={{ margin: 0, fontSize: 13.5, color: "var(--ink-soft)" }}>{o.texto}</p>
              {!disponible && (
                <p style={{ margin: "8px 0 0", fontSize: 13, color: "var(--amber)" }}>{o.sinContrato}</p>
              )}
            </div>
            <button type="button" role="switch" aria-checked={activa && disponible}
                    aria-label={o.titulo}
                    disabled={!disponible || guardando === o.clave}
                    onClick={() => cambiar(o.clave, !activa)}
                    style={{
                      flexShrink: 0, width: 46, height: 26, borderRadius: 999, border: "none",
                      padding: 3, cursor: disponible ? "pointer" : "not-allowed",
                      background: activa && disponible ? "var(--petrol)" : "var(--line-strong)",
                      opacity: disponible ? 1 : 0.5,
                      transition: "background var(--dur-fast) var(--ease)",
                    }}>
              <span style={{
                display: "block", width: 20, height: 20, borderRadius: "50%", background: "#fff",
                transform: `translateX(${activa && disponible ? 20 : 0}px)`,
                transition: "transform var(--dur-fast) var(--ease)",
              }} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
