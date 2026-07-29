"use client";

/**
 * Botón "Regresar" (Sprint 45).
 *
 * Usa el historial del navegador cuando existe; si la persona llegó por
 * enlace directo (sin historial dentro de la app) cae a la ruta indicada
 * en `fallback`, de modo que nunca deja al usuario fuera del panel.
 */

export default function BackButton({ fallback = "/panel/", label = "Regresar" }) {
  function goBack() {
    if (typeof window === "undefined") return;
    if (window.history.length > 1) window.history.back();
    else window.location.href = fallback;
  }

  return (
    <button type="button" onClick={goBack} className="btn btn-ghost"
            style={{ padding: "6px 12px", fontSize: 13, marginBottom: 12 }}
            aria-label={label} title={label}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M15 5l-7 7 7 7" />
      </svg>
      {label}
    </button>
  );
}
