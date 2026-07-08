"use client";

/**
 * Modal de confirmación con el diseño del sistema (reemplaza el
 * window.confirm nativo, que muestra la URL del servidor y no se
 * puede estilizar).
 *
 * Uso:
 *   const [confirm, ConfirmUI] = useConfirm();
 *   ...
 *   const ok = await confirm({ title, message, confirmLabel, danger });
 *   ...
 *   return <>{ConfirmUI} ...resto...</>
 */

import { useCallback, useState } from "react";

export function useConfirm() {
  const [state, setState] = useState(null); // {title, message, confirmLabel, danger, resolve}

  const confirm = useCallback((opts) => {
    return new Promise((resolve) => setState({ ...opts, resolve }));
  }, []);

  function close(answer) {
    state?.resolve(answer);
    setState(null);
  }

  const ui = state ? (
    <div style={overlay} role="dialog" aria-modal="true" aria-label={state.title}
         onClick={(e) => { if (e.target === e.currentTarget) close(false); }}>
      <div style={box}>
        <h3 style={{ marginBottom: 8 }}>{state.title}</h3>
        <p style={{ fontSize: 14, color: "var(--ink-soft)", whiteSpace: "pre-line", marginBottom: 20 }}>
          {state.message}
        </p>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => close(false)} autoFocus>
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            style={state.danger ? { background: "var(--red)" } : {}}
            onClick={() => close(true)}
          >
            {state.confirmLabel || "Confirmar"}
          </button>
        </div>
      </div>
    </div>
  ) : null;

  return [confirm, ui];
}

const overlay = {
  position: "fixed", inset: 0, background: "rgba(22,40,43,.45)",
  display: "flex", alignItems: "center", justifyContent: "center",
  zIndex: 100, padding: 20,
};
const box = {
  background: "#fff", borderRadius: 14, padding: "22px 24px",
  maxWidth: 440, width: "100%", boxShadow: "0 18px 50px rgba(0,0,0,.22)",
};
