"use client";

/**
 * Botón de dictado para la nota clínica.
 * ────────────────────────────────────────────────────────────────────
 * Usa el reconocimiento de voz del propio navegador (Web Speech API):
 * no hay que instalar nada, registrarse en ningún servicio ni pagar.
 *
 * Lo que conviene saber, y lo que se le dice al usuario en pantalla:
 * el navegador no transcribe en el equipo. **Chrome y Edge envían el
 * audio a los servidores de Google o Microsoft, y Safari a los de
 * Apple** (a veces lo resuelve en el equipo). Firefox no lo soporta.
 * El orden en secciones sí se hace aquí, sin ningún servicio externo
 * (ver `secciones.mjs`).
 *
 * El texto NO se guarda solo: al detener el dictado se escribe en el
 * campo de notas y el profesional lo revisa antes de pulsar Guardar.
 */

import { useEffect, useRef, useState } from "react";

import { SECCIONES, aTextoNota, aplicarPuntuacion, detectarSeccion, organizarDictado } from "./secciones.mjs";

const ERRORES = {
  "not-allowed": "El navegador no tiene permiso para usar el micrófono. Actívalo en el candado de la barra de direcciones.",
  "service-not-allowed": "El navegador no permite el dictado en esta página. Hace falta abrir el panel con https (o en localhost).",
  "audio-capture": "No se encontró ningún micrófono.",
  network: "No hay conexión con el servicio de voz del navegador. El dictado necesita internet.",
  "language-not-supported": "El navegador no reconoce el español en este equipo.",
};

function reconocedor() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function idioma() {
  const nav = typeof navigator !== "undefined" ? navigator.language || "" : "";
  return nav.toLowerCase().startsWith("es") ? nav : "es-ES";
}

/**
 * @param conSecciones  ordenar en motivo / hallazgos / procedimiento /
 *                      indicaciones (nota clínica) o dictado corrido
 * @param onTexto       recibe el texto final al detener
 */
export default function Dictado({ conSecciones = true, onTexto }) {
  const [estado, setEstado] = useState("inactivo");   // inactivo | escuchando | error
  const [frases, setFrases] = useState([]);
  const [parcial, setParcial] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [soportado, setSoportado] = useState(true);
  const rec = useRef(null);
  const activo = useRef(false);     // el usuario quiere seguir dictando
  const acumuladas = useRef([]);    // frases finales, sin esperar al render
  const onTextoRef = useRef(onTexto);
  useEffect(() => { onTextoRef.current = onTexto; }, [onTexto]);

  // Se comprueba en el navegador, no en el primer render (SSR).
  useEffect(() => { setSoportado(Boolean(reconocedor())); }, []);
  useEffect(() => () => { activo.current = false; rec.current?.abort?.(); }, []);

  function entregar() {
    const lista = acumuladas.current;
    if (!lista.length) return;
    const texto = conSecciones
      ? aTextoNota(organizarDictado(lista))
      : aplicarPuntuacion(lista.join(" ")).replace(/^\p{Ll}/u, (l) => l.toUpperCase());
    if (texto) onTextoRef.current?.(texto);
  }

  function empezar() {
    const Clase = reconocedor();
    if (!Clase) { setSoportado(false); return; }
    if (typeof window !== "undefined" && window.isSecureContext === false) {
      setEstado("error"); setMensaje(ERRORES["service-not-allowed"]); return;
    }
    const r = new Clase();
    r.lang = idioma();
    r.continuous = true;
    r.interimResults = true;

    r.onresult = (e) => {
      let interino = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          acumuladas.current = [...acumuladas.current, t.trim()];
        } else {
          interino += t;
        }
      }
      setFrases(acumuladas.current);
      setParcial(interino.trim());
    };
    r.onerror = (e) => {
      // «no-speech» es un silencio largo: no es un error para el usuario.
      if (e.error === "no-speech" || e.error === "aborted") return;
      activo.current = false;
      setEstado("error");
      setMensaje(ERRORES[e.error] || `El dictado se detuvo (${e.error}).`);
    };
    r.onend = () => {
      // Chrome corta el reconocimiento tras unos segundos de silencio
      // aunque se le pida continuo: si el usuario no ha pulsado
      // Detener, se vuelve a arrancar sin que lo note.
      if (activo.current) {
        try { r.start(); return; } catch { /* ya estaba arrancando */ }
      }
      setParcial("");
      setEstado((s) => (s === "error" ? s : "inactivo"));
      entregar();
      acumuladas.current = [];
    };

    acumuladas.current = [];
    setFrases([]); setParcial(""); setMensaje("");
    activo.current = true;
    rec.current = r;
    try {
      r.start();
      setEstado("escuchando");
    } catch {
      activo.current = false;
      setEstado("error");
      setMensaje("No se pudo iniciar el dictado.");
    }
  }

  function detener() {
    activo.current = false;
    // `stop` (no `abort`): deja que llegue el resultado de la última
    // frase antes de `onend`, que es donde se entrega el texto.
    rec.current?.stop();
  }

  if (!soportado) {
    return (
      <p style={{ fontSize: 12, color: "var(--ink-faint)", margin: "0 0 8px" }}>
        Este navegador no permite dictar. Usa Chrome, Edge o Safari.
      </p>
    );
  }

  const escuchando = estado === "escuchando";
  // Sección en la que se está escribiendo ahora, para enseñarla.
  let actual = "motivo";
  for (const f of [...frases, parcial]) {
    const d = f && detectarSeccion(f);
    if (d) actual = d.seccion;
  }
  const vista = conSecciones ? organizarDictado(parcial ? [...frases, parcial] : frases) : null;

  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <button type="button" onClick={escuchando ? detener : empezar}
                className={`btn ${escuchando ? "btn-danger" : "btn-ghost"}`}
                aria-pressed={escuchando}
                style={{ fontSize: 12.5, padding: "4px 12px", display: "inline-flex", alignItems: "center", gap: 6 }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
          </svg>
          {escuchando ? "Detener dictado" : "Dictar"}
        </button>
        {escuchando && conSecciones && (
          <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>
            Escribiendo en <strong>{SECCIONES.find((s) => s.clave === actual)?.titulo}</strong>
          </span>
        )}
      </div>

      {escuchando && (
        <div className="animate-rise" style={{ marginTop: 8, padding: "8px 10px", borderRadius: 8,
                                                background: "var(--paper)", border: "1px solid var(--line)",
                                                fontSize: 12.5 }}>
          {conSecciones ? SECCIONES.map((s) => (
            <div key={s.clave} style={{ opacity: vista[s.clave] ? 1 : 0.45 }}>
              <strong>{s.titulo}:</strong> {vista[s.clave] || "—"}
            </div>
          )) : (
            <div>{[...frases, parcial].filter(Boolean).join(" ") || "Escuchando…"}</div>
          )}
          {conSecciones && (
            <p style={{ margin: "6px 0 0", fontSize: 11.5, color: "var(--ink-faint)" }}>
              Para cambiar de sección, empieza la frase con «motivo», «hallazgos»,
              «procedimiento» o «indicaciones». «Punto y seguido» y «punto y aparte» puntúan.
            </p>
          )}
        </div>
      )}

      {mensaje && <p style={{ fontSize: 12, color: "var(--red)", margin: "6px 0 0" }}>{mensaje}</p>}
      <p style={{ fontSize: 11, color: "var(--ink-faint)", margin: "6px 0 0" }}>
        La voz la transcribe el servicio del navegador (Google en Chrome, Apple en Safari). El texto
        queda en el campo para que lo revises antes de guardar.
      </p>
    </div>
  );
}
