"use client";

import { useEffect, useState } from "react";
import { currentUser, logout } from "../../lib/api";

// Navegación por rol (matriz de permisos del SRS)
const NAV = [
  { href: "/panel/plataforma/", label: "Clínicas", roles: ["superadmin"] },
  { href: "/panel/", label: "Inicio", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { href: "/panel/pacientes/", label: "Pacientes", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { href: "/panel/agenda/", label: "Agenda", roles: ["admin", "reception", "doctor"] },
  { href: "/panel/pagos/", label: "Pagos", roles: ["admin", "reception"] },
  { href: "/panel/inventario/", label: "Inventario", roles: ["admin", "auxiliary"] },
  { href: "/panel/reportes/", label: "Reportes", roles: ["admin"] },
  { href: "/panel/configuracion/", label: "Configuración", roles: ["admin"] },
];

const ROLE_LABELS = {
  superadmin: "Super Administrador", admin: "Administrador",
  reception: "Recepción", doctor: "Doctor/a", auxiliary: "Auxiliar",
};

export default function PanelLayout({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const u = currentUser();
    if (!u) { window.location.href = "/login/"; return; }
    setUser(u);
    setReady(true);
  }, []);

  if (!ready) return null;

  const items = NAV.filter((n) => n.roles.includes(user.role));
  const path = typeof window !== "undefined" ? window.location.pathname : "";

  return (
    <div style={styles.shell}>
      <aside style={styles.sidebar}>
        <div style={styles.logo}>
          <span style={{ fontSize: 26, color: "var(--mint)" }} aria-hidden="true">◠</span>
          <span style={styles.logoText}>Clínica</span>
        </div>

        <nav style={{ flex: 1 }}>
          {items.map((item) => {
            const active = path === item.href;
            return (
              <a key={item.href} href={item.href}
                 style={{ ...styles.navItem, ...(active ? styles.navActive : {}) }}>
                {item.label}
              </a>
            );
          })}
        </nav>

        <div style={styles.userBox}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{user.full_name || user.email}</div>
          <div style={{ fontSize: 12, color: "var(--mint)" }}>{ROLE_LABELS[user.role] || user.role}</div>
          <button onClick={logout} style={styles.logoutBtn}>Cerrar sesión</button>
        </div>
      </aside>

      <main style={styles.main}>{children}</main>
    </div>
  );
}

const styles = {
  shell: { display: "flex", minHeight: "100vh" },
  sidebar: {
    flex: "0 0 220px", background: "var(--petrol-deep)", color: "#fff",
    display: "flex", flexDirection: "column", padding: "20px 14px",
    position: "sticky", top: 0, height: "100vh",
  },
  logo: { display: "flex", alignItems: "center", gap: 10, padding: "4px 10px 22px" },
  logoText: { fontWeight: 700, fontSize: 18, letterSpacing: "-0.01em" },
  navItem: {
    display: "block", padding: "10px 12px", borderRadius: 8,
    color: "rgba(255,255,255,.82)", fontSize: 14, fontWeight: 500, marginBottom: 2,
  },
  navActive: { background: "var(--petrol)", color: "#fff" },
  userBox: { borderTop: "1px solid rgba(255,255,255,.15)", paddingTop: 14, marginTop: 14 },
  logoutBtn: {
    marginTop: 10, background: "transparent", border: "1px solid rgba(255,255,255,.3)",
    color: "#fff", borderRadius: 8, padding: "6px 12px", fontSize: 13, width: "100%",
  },
  main: { flex: 1, padding: "28px 32px", maxWidth: 1200 },
};
