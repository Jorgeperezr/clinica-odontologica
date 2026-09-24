"use client";

/**
 * Elegir la propia contraseña.
 *
 * Existe por la mitad de la entrega de credenciales que no es del Super
 * Administrador sino de la clínica: mientras la contraseña sea la que
 * puso otro, el backend bloquea la cuenta entera (403
 * `password_change_required`). Sin esta pantalla ese bloqueo no tendría
 * salida —todas las demás fallarían con un mensaje imposible de
 * obedecer— y la cuenta recién entregada quedaría inservible.
 *
 * Dos modos, y la diferencia importa:
 *
 *   - **Contraseña temporal**: NO se pide la actual. Pedírsela sería
 *     pedirle al administrador de la clínica que repita el secreto que
 *     se inventó otra persona, que es justo lo que viene a dejar de
 *     usar.
 *   - **Cambio voluntario**: sí se pide, porque si no bastaría con una
 *     sesión abierta y sin vigilar para quedarse con la cuenta.
 */

import { useEffect, useState } from "react";
import { api, cambiarContrasena, currentUser, logout } from "../../lib/api";

export default function CambiarContrasenaPage() {
  const [obligatorio, setObligatorio] = useState(null);   // null = averiguándolo
  const [quien, setQuien] = useState("");
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  // Se pregunta al servidor en vez de fiarse del perfil guardado: si la
  // contraseña la acaban de restablecer, lo que hay en localStorage es
  // de antes de ese restablecimiento.
  useEffect(() => {
    const guardado = currentUser();
    if (guardado) { setQuien(guardado.email || ""); setObligatorio(!!guardado.must_change_password); }
    api("/auth/me/")
      .then(async (r) => {
        if (!r.ok) return;
        const yo = await r.json();
        setQuien(yo.email || "");
        setObligatorio(!!yo.must_change_password);
      })
      .catch(() => { if (!guardado) setObligatorio(false); });
  }, []);

  async function enviar(e) {
    e.preventDefault();
    setError("");
    if (nueva !== repetida) { setError("Las dos contraseñas no coinciden."); return; }
    setGuardando(true);
    try {
      await cambiarContrasena(obligatorio ? "" : actual, nueva);
      window.location.href = "/panel/";
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  }

  if (obligatorio === null) return <div className="empty" style={{ marginTop: 80 }}>Cargando…</div>;

  return (
    <div style={estilos.wrap}>
      <div style={estilos.marca}>
        <div style={estilos.marcaInterior}>
          <div style={estilos.diente} aria-hidden="true">◠</div>
          <h1 style={estilos.marcaTitulo}>Clínica<br />Odontológica</h1>
          <p style={estilos.marcaSub}>Sistema de gestión clínica</p>
        </div>
      </div>

      <div style={estilos.ladoForm}>
        <form onSubmit={enviar} style={estilos.form}>
          <h2 style={{ marginBottom: 6 }}>
            {obligatorio ? "Elige tu contraseña" : "Cambiar contraseña"}
          </h2>
          <p style={{ color: "var(--ink-soft)", marginBottom: 20, fontSize: 14 }}>
            {obligatorio ? (
              <>
                Entraste con una contraseña temporal que generó la plataforma.
                Elige la tuya para continuar: <strong>a partir de ese momento,
                nadie más que tú la conoce.</strong>
              </>
            ) : (
              <>Cuenta <strong>{quien}</strong>.</>
            )}
          </p>

          {error && <div className="error-box">{error}</div>}

          {!obligatorio && (
            <div className="field">
              <label htmlFor="actual">Contraseña actual</label>
              <input id="actual" type="password" required autoComplete="current-password"
                     value={actual} onChange={(e) => setActual(e.target.value)} />
            </div>
          )}

          <div className="field">
            <label htmlFor="nueva">Contraseña nueva</label>
            <input id="nueva" type="password" required minLength={10} autoComplete="new-password"
                   value={nueva} onChange={(e) => setNueva(e.target.value)} />
            <small style={{ color: "var(--ink-soft)", fontSize: 12 }}>
              Al menos 10 caracteres. No puede ser la temporal ni una contraseña común.
            </small>
          </div>

          <div className="field">
            <label htmlFor="repetida">Repítela</label>
            <input id="repetida" type="password" required autoComplete="new-password"
                   value={repetida} onChange={(e) => setRepetida(e.target.value)} />
          </div>

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }}
                  disabled={guardando}>
            {guardando ? "Guardando…" : "Guardar y continuar"}
          </button>

          <button type="button" className="btn btn-ghost"
                  style={{ width: "100%", justifyContent: "center", marginTop: 10, fontSize: 13 }}
                  onClick={logout}>
            {obligatorio ? "Salir sin cambiarla" : "Cancelar"}
          </button>
        </form>
      </div>
    </div>
  );
}

const estilos = {
  wrap: { display: "flex", minHeight: "100vh" },
  marca: {
    flex: "0 0 42%", background: "var(--petrol-deep)", color: "#fff",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 40,
  },
  marcaInterior: { maxWidth: 320 },
  diente: { fontSize: 64, lineHeight: 1, color: "var(--mint)", marginBottom: 18 },
  marcaTitulo: { color: "#fff", fontSize: 40, lineHeight: 1.1, fontWeight: 700, letterSpacing: "-0.02em" },
  marcaSub: { marginTop: 12, color: "var(--mint)", fontSize: 15 },
  ladoForm: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  form: { width: "100%", maxWidth: 380 },
};
