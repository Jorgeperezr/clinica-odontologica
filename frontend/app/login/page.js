"use client";

import { useEffect, useState } from "react";
import { login, RUTA_CAMBIO } from "../../lib/api";
import { LEMA, LogoClinube } from "../../lib/marca";
import { initColorMode } from "../../lib/theme";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Todavía no hay clínica: paleta de Clinube, con el modo y el «Sin
  // color» que la persona tenga elegidos en este navegador.
  useEffect(() => initColorMode(), []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const sesion = await login(email, password);
      // Entrar con una contraseña temporal funciona —si no, no habría
      // forma de cambiarla—, pero el panel entero está bloqueado hasta
      // que se elija la propia, así que se va derecho allí en vez de a
      // un escritorio donde todo fallaría.
      window.location.href = sesion?.must_change_password ? RUTA_CAMBIO : "/panel/";
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.brandSide}>
        <div style={styles.brandInner}>
          <h1 style={styles.brandTitle}><LogoClinube alto={58} tinta="#ffffff" acento="var(--mint)" /></h1>
          <p style={styles.brandSub}>{LEMA}</p>
        </div>
      </div>

      <div style={styles.formSide}>
        <form onSubmit={handleSubmit} style={styles.form}>
          <h2 style={{ marginBottom: 6 }}>Iniciar sesión</h2>
          <p style={{ color: "var(--ink-soft)", marginBottom: 22, fontSize: 14 }}>
            Acceso para el personal de la clínica
          </p>

          {error && <div className="error-box">{error}</div>}

          <div className="field">
            <label htmlFor="email">Correo electrónico</label>
            <input
              id="email" type="email" required autoComplete="username"
              value={email} onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Contraseña</label>
            <input
              id="password" type="password" required autoComplete="current-password"
              value={password} onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} disabled={loading}>
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles = {
  wrap: { display: "flex", minHeight: "100vh" },
  brandSide: {
    flex: "0 0 42%", background: "var(--nav-bg)", color: "#fff",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 40,
  },
  brandInner: { maxWidth: 320 },
  brandTitle: { margin: 0 },
  brandSub: { marginTop: 12, color: "var(--mint)", fontSize: 15 },
  formSide: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  form: { width: "100%", maxWidth: 380 },
};
