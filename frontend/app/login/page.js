"use client";

import { useState } from "react";
import { login } from "../../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      window.location.href = "/panel/";
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
          <div style={styles.tooth} aria-hidden="true">◠</div>
          <h1 style={styles.brandTitle}>Clínica<br />Odontológica</h1>
          <p style={styles.brandSub}>Sistema de gestión clínica</p>
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
    flex: "0 0 42%", background: "var(--petrol-deep)", color: "#fff",
    display: "flex", alignItems: "center", justifyContent: "center", padding: 40,
  },
  brandInner: { maxWidth: 320 },
  tooth: { fontSize: 64, lineHeight: 1, color: "var(--mint)", marginBottom: 18 },
  brandTitle: { fontSize: 40, lineHeight: 1.1, fontWeight: 700, letterSpacing: "-0.02em" },
  brandSub: { marginTop: 12, color: "var(--mint)", fontSize: 15 },
  formSide: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 },
  form: { width: "100%", maxWidth: 380 },
};
