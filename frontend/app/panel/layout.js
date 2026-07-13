"use client";

import { useEffect, useState } from "react";
import { currentUser, logout } from "../../lib/api";

// Navegación por rol (matriz de permisos del SRS)
const NAV = [
  { href: "/panel/plataforma/", label: "Plataforma", icon: "◫", roles: ["superadmin"] },
  { href: "/panel/", label: "Inicio", icon: "⌂", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { href: "/panel/pacientes/", label: "Pacientes", icon: "☺", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { href: "/panel/agenda/", label: "Agenda", icon: "▤", roles: ["admin", "reception", "doctor"] },
  { href: "/panel/firma/", label: "Mi firma", icon: "✎", roles: ["doctor"] },
  { href: "/panel/pagos/", label: "Pagos", icon: "$", roles: ["admin", "reception"] },
  { href: "/panel/inventario/", label: "Inventario", icon: "▦", roles: ["admin", "auxiliary"] },
  { href: "/panel/reportes/", label: "Reportes", icon: "▨", roles: ["admin"] },
  { href: "/panel/configuracion/", label: "Configuración", icon: "⚙", roles: ["admin"] },
];

const ROLE_LABELS = {
  superadmin: "Super Administrador", admin: "Administrador",
  reception: "Recepción", doctor: "Doctor/a", auxiliary: "Auxiliar",
};

export default function PanelLayout({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const u = currentUser();
    if (!u) { window.location.href = "/login/"; return; }
    setUser(u);
    setReady(true);
    // Recordar la preferencia de menú colapsado
    try {
      const saved = localStorage.getItem("sidebarCollapsed");
      if (saved === "1") setCollapsed(true);
    } catch { /* SSR / sin storage */ }
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("sidebarCollapsed", next ? "1" : "0"); } catch {}
      return next;
    });
  }

  if (!ready) return null;

  const items = NAV.filter((n) => n.roles.includes(user.role));
  const path = typeof window !== "undefined" ? window.location.pathname : "";
  const W = collapsed ? 64 : 220;

  return (
    <div style={styles.shell}>
      <aside style={{ ...styles.sidebar, flexBasis: W, width: W }}>
        <div style={{ ...styles.logo, justifyContent: collapsed ? "center" : "flex-start" }}>
          <span style={{ fontSize: 26, color: "var(--mint)" }} aria-hidden="true">◠</span>
          {!collapsed && <span style={styles.logoText}>Clínica</span>}
        </div>

        <button onClick={toggleCollapsed} style={styles.collapseBtn}
                aria-label={collapsed ? "Expandir menú" : "Contraer menú"}
                title={collapsed ? "Expandir menú" : "Contraer menú"}>
          {collapsed ? "»" : "«"}
        </button>

        <nav style={{ flex: 1, marginTop: 6 }}>
          {items.map((item) => {
            const active = path === item.href;
            return (
              <a key={item.href} href={item.href} title={collapsed ? item.label : undefined}
                 style={{ ...styles.navItem,
                          justifyContent: collapsed ? "center" : "flex-start",
                          padding: collapsed ? "10px 0" : "10px 12px",
                          ...(active ? styles.navActive : {}) }}>
                <span style={{ fontSize: 16, width: collapsed ? "auto" : 20, textAlign: "center" }}
                      aria-hidden="true">{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </a>
            );
          })}
        </nav>

        <div style={styles.userBox}>
          {!collapsed && (
            <>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{user.full_name || user.email}</div>
              <div style={{ fontSize: 12, color: "var(--mint)" }}>{ROLE_LABELS[user.role] || user.role}</div>
            </>
          )}
          <button onClick={logout} style={styles.logoutBtn}
                  title="Cerrar sesión">
            {collapsed ? "⎋" : "Cerrar sesión"}
          </button>
        </div>
      </aside>

      <main style={styles.main}>
        <div style={styles.contentWrap}>{children}</div>
      </main>
    </div>
  );
}

const styles = {
  shell: { display: "flex", minHeight: "100vh" },
  sidebar: {
    flexGrow: 0, flexShrink: 0, background: "var(--petrol-deep)", color: "#fff",
    display: "flex", flexDirection: "column", padding: "20px 10px",
    position: "sticky", top: 0, height: "100vh",
    transition: "width .18s ease, flex-basis .18s ease",
  },
  logo: { display: "flex", alignItems: "center", gap: 10, padding: "4px 6px 10px" },
  logoText: { fontWeight: 700, fontSize: 18, letterSpacing: "-0.01em" },
  collapseBtn: {
    alignSelf: "flex-end", background: "rgba(255,255,255,.1)", border: "none",
    color: "#fff", borderRadius: 6, width: 26, height: 26, cursor: "pointer",
    fontSize: 14, lineHeight: 1, marginBottom: 4,
  },
  navItem: {
    display: "flex", alignItems: "center", gap: 11, borderRadius: 8,
    color: "rgba(255,255,255,.82)", fontSize: 14, fontWeight: 500, marginBottom: 2,
    whiteSpace: "nowrap", overflow: "hidden",
  },
  navActive: { background: "var(--petrol)", color: "#fff" },
  userBox: { borderTop: "1px solid rgba(255,255,255,.15)", paddingTop: 14, marginTop: 14 },
  logoutBtn: {
    marginTop: 10, background: "transparent", border: "1px solid rgba(255,255,255,.3)",
    color: "#fff", borderRadius: 8, padding: "6px 12px", fontSize: 13, width: "100%",
    cursor: "pointer",
  },
  // Main ahora ocupa TODO el ancho restante y centra su contenido.
  main: { flex: 1, minWidth: 0, padding: "28px clamp(16px, 3vw, 40px)", display: "flex", justifyContent: "center" },
  contentWrap: { width: "100%", maxWidth: 1200 },
};
