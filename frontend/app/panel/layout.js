"use client";

import { useEffect, useState } from "react";
import { api, currentUser, logout } from "../../lib/api";
import { applyBrandingChrome, applyTheme, initColorMode, logoSrc, onBrandingUpdated, readBrandingCache, saveBrandingCache } from "../../lib/theme";
import NavIcon from "../../lib/NavIcons";
import ThemeSwitch from "../../lib/ThemeSwitch";

// Navegación por rol (matriz de permisos del SRS)
const NAV = [
  { href: "/panel/plataforma/", label: "Plataforma", iconName: "plataforma", roles: ["superadmin"] },
  { href: "/panel/", label: "Inicio", iconName: "inicio", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { href: "/panel/pacientes/", label: "Pacientes", iconName: "pacientes", roles: ["admin", "reception", "doctor", "auxiliary"] },
  { href: "/panel/agenda/", label: "Agenda", iconName: "agenda", roles: ["admin", "reception", "doctor"] },
  { href: "/panel/firma/", label: "Mi firma", iconName: "firma", roles: ["doctor"] },
  { href: "/panel/pagos/", label: "Pagos", iconName: "pagos", roles: ["admin", "reception"] },
  { href: "/panel/inventario/", label: "Inventario", iconName: "inventario", roles: ["admin", "auxiliary"] },
  { href: "/panel/reportes/", label: "Reportes", iconName: "reportes", roles: ["admin"] },
  { href: "/panel/configuracion/", label: "Configuración", iconName: "configuracion", roles: ["admin"] },
];

const ROLE_LABELS = {
  superadmin: "Super Administrador", admin: "Administrador",
  reception: "Recepción", doctor: "Doctor/a", auxiliary: "Auxiliar",
};

export default function PanelLayout({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [branding, setBranding] = useState(null);
  const [isMobile, setIsMobile] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const u = currentUser();
    if (!u) { window.location.href = "/login/"; return; }
    setUser(u);
    setReady(true);
    // Apariencia (claro/oscuro/sistema) antes de pintar la marca, para
    // que los tonos se deriven ya con el modo correcto.
    const stopColorMode = initColorMode();

    // Identidad visual por clínica: pintado instantáneo desde caché,
    // refresco desde la API y actualización en vivo al guardar cambios.
    const cached = readBrandingCache();
    if (cached) {
      setBranding(cached);
      applyTheme(cached.theme);
      applyBrandingChrome(cached);
    }
    (async () => {
      try {
        const resp = await api("/config/branding/");
        if (resp.ok) {
          const b = await resp.json();
          setBranding(b);
          applyTheme(b.theme);
          applyBrandingChrome(b);
          saveBrandingCache(b);
        }
      } catch { /* sin identidad: tema del sistema */ }
    })();
    const unsubscribe = onBrandingUpdated((b) => {
      setBranding(b);
      applyTheme(b.theme);
      applyBrandingChrome(b);
    });
    return () => { unsubscribe(); stopColorMode(); };
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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(max-width: 860px)");
    const apply = () => { setIsMobile(mq.matches); if (!mq.matches) setDrawerOpen(false); };
    apply();
    mq.addEventListener?.("change", apply);
    return () => mq.removeEventListener?.("change", apply);
  }, []);

  // Con el panel abierto se bloquea el desplazamiento del fondo
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.style.overflow = (isMobile && drawerOpen) ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [isMobile, drawerOpen]);

  if (!ready) return null;

  const items = NAV.filter((n) => n.roles.includes(user.role));
  const path = typeof window !== "undefined" ? window.location.pathname : "";
  const W = isMobile ? 264 : (collapsed ? 64 : 220);

  return (
    <div style={{ ...styles.shell, flexDirection: isMobile ? "column" : "row" }}>
      {/* Barra superior: solo en pantallas estrechas */}
      {isMobile && (
        <header style={styles.topbar}>
          <button onClick={() => setDrawerOpen(true)} style={styles.iconBtn}
                  aria-label="Abrir menú" title="Menú">
            <MenuIcon />
          </button>
          {branding?.logo_url && (
            <img src={logoSrc(branding.logo_url, branding.updated_at)} alt=""
                 style={{ height: 26, maxWidth: 40, objectFit: "contain" }} />
          )}
          <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-.01em",
                         overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {branding?.short_name || branding?.display_name || "Clínica"}
          </span>
        </header>
      )}

      {/* Fondo oscurecido al abrir el panel */}
      {isMobile && drawerOpen && (
        <div className="animate-fade" onClick={() => setDrawerOpen(false)}
             style={styles.backdrop} aria-hidden="true" />
      )}

      <aside style={{
               ...styles.sidebar, flexBasis: W, width: W,
               ...(isMobile ? {
                 position: "fixed", top: 0, left: 0, zIndex: 60,
                 transform: drawerOpen ? "translateX(0)" : "translateX(-100%)",
                 transition: "transform .22s var(--ease)",
                 boxShadow: drawerOpen ? "var(--shadow-lg)" : "none",
               } : {}),
             }}>
        <div style={{ ...styles.logo, justifyContent: (collapsed && !isMobile) ? "center" : "flex-start" }}>
          {branding?.logo_url ? (
            <img src={logoSrc(branding.logo_url, branding.updated_at)} alt="Logotipo de la clínica"
                 style={{ height: (collapsed && !isMobile) ? 32 : 40, maxWidth: (collapsed && !isMobile) ? 46 : 70,
                          objectFit: "contain" }} />
          ) : (
            <span style={{ fontSize: 26, color: "var(--mint)" }} aria-hidden="true">◠</span>
          )}
          {(!collapsed || isMobile) && (
            <span style={{ ...styles.logoText, fontSize: 15, lineHeight: 1.15,
                           overflow: "hidden", display: "-webkit-box",
                           WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
              {branding?.short_name || branding?.display_name || "Clínica"}
            </span>
          )}
        </div>

        {isMobile ? (
          <button onClick={() => setDrawerOpen(false)} style={styles.collapseBtn}
                  aria-label="Cerrar menú" title="Cerrar menú">
            <CloseIcon />
          </button>
        ) : (
          <button onClick={toggleCollapsed} style={styles.collapseBtn}
                  aria-label={collapsed ? "Expandir menú" : "Contraer menú"}
                  title={collapsed ? "Expandir menú" : "Contraer menú"}>
            <ChevronIcon open={!collapsed} />
          </button>
        )}

        <nav style={{ flex: 1, marginTop: 6 }}>
          {items.map((item) => {
            const active = path === item.href;
            return (
              <a key={item.href} href={item.href} title={collapsed ? item.label : undefined}
                 onClick={() => isMobile && setDrawerOpen(false)}
                 style={{ ...styles.navItem,
                          justifyContent: (collapsed && !isMobile) ? "center" : "flex-start",
                          padding: (collapsed && !isMobile) ? "12px 0" : "11px 12px",
                          ...(active ? styles.navActive : {}) }}>
                <span style={{ display: "inline-flex", width: (collapsed && !isMobile) ? "auto" : 20,
                             justifyContent: "center", flexShrink: 0 }} aria-hidden="true">
                  <NavIcon name={item.iconName} />
                </span>
                {(!collapsed || isMobile) && <span>{item.label}</span>}
              </a>
            );
          })}
        </nav>

        <div style={{ marginTop: 14 }}>
          <ThemeSwitch compact={collapsed && !isMobile} />
        </div>

        <div style={styles.userBox}>
          {(!collapsed || isMobile) && (
            <>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{user.full_name || user.email}</div>
              <div style={{ fontSize: 12, color: "var(--mint)" }}>{ROLE_LABELS[user.role] || user.role}</div>
            </>
          )}
          <button onClick={logout} style={styles.logoutBtn}
                  title="Cerrar sesión">
            {(collapsed && !isMobile) ? "⎋" : "Cerrar sesión"}
          </button>
        </div>
      </aside>

      <main style={styles.main}>
        <div style={styles.contentWrap}>{children}</div>
      </main>
    </div>
  );
}

/* Iconos de navegación del armazón: mismo trazo que NavIcons. */
const strokeIcon = {
  viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.9, strokeLinecap: "round", strokeLinejoin: "round",
};
function MenuIcon() {
  return <svg width="22" height="22" {...strokeIcon}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
}
function CloseIcon() {
  return <svg width="18" height="18" {...strokeIcon}><path d="M6 6l12 12M18 6L6 18" /></svg>;
}
/* Doble punta de flecha: indica plegar/desplegar sin depender de glifos
   de texto, que se veían descentrados y de tamaño irregular. */
function ChevronIcon({ open }) {
  return (
    <svg width="16" height="16" {...strokeIcon}
         style={{ transform: open ? "none" : "rotate(180deg)", transition: "transform .2s var(--ease)" }}>
      <path d="M13 6l-5 6 5 6M18.5 6l-5 6 5 6" />
    </svg>
  );
}

const styles = {
  shell: { display: "flex", minHeight: "100vh" },
  sidebar: {
    flexGrow: 0, flexShrink: 0, background: "var(--nav-bg)", color: "var(--nav-ink)",
    display: "flex", flexDirection: "column", padding: "20px 10px",
    position: "sticky", top: 0, height: "100vh",
    transition: "width .18s ease, flex-basis .18s ease",
  },
  logo: { display: "flex", alignItems: "center", gap: 10, padding: "4px 6px 10px" },
  logoText: { fontWeight: 700, fontSize: 18, letterSpacing: "-0.01em" },
  // Contraer: círculo centrado en su fila, con el icono centrado dentro.
  collapseBtn: {
    alignSelf: "center", background: "var(--nav-hover)",
    border: "1px solid var(--nav-line)", color: "var(--nav-ink)",
    borderRadius: 999, width: 30, height: 30, cursor: "pointer",
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    padding: 0, marginBottom: 10,
    transition: "background var(--dur-fast) var(--ease)",
  },
  topbar: {
    position: "sticky", top: 0, zIndex: 40,
    display: "flex", alignItems: "center", gap: 10,
    padding: "10px 14px", background: "var(--nav-bg)", color: "var(--nav-ink)",
    borderBottom: "1px solid var(--nav-line)",
  },
  iconBtn: {
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    width: 38, height: 38, borderRadius: 10, flexShrink: 0,
    background: "transparent", border: "1px solid var(--nav-line)",
    color: "var(--nav-ink)", cursor: "pointer", padding: 0,
  },
  backdrop: {
    position: "fixed", inset: 0, zIndex: 55, background: "var(--overlay)",
  },
  navItem: {
    display: "flex", alignItems: "center", gap: 11, borderRadius: 8,
    color: "var(--nav-ink-soft)", fontSize: 14, fontWeight: 500, marginBottom: 2,
    whiteSpace: "nowrap", overflow: "hidden",
  },
  navActive: { background: "var(--petrol)", color: "var(--nav-active-ink)" },
  userBox: { borderTop: "1px solid var(--nav-line)", paddingTop: 14, marginTop: 14 },
  logoutBtn: {
    marginTop: 10, background: "transparent", border: "1px solid var(--nav-line)",
    color: "#fff", borderRadius: 8, padding: "6px 12px", fontSize: 13, width: "100%",
    cursor: "pointer",
  },
  // Main ahora ocupa TODO el ancho restante y centra su contenido.
  main: { flex: 1, minWidth: 0, width: "100%", padding: "clamp(16px, 3vw, 28px) clamp(14px, 3vw, 40px)", display: "flex", justifyContent: "center" },
  contentWrap: { width: "100%", maxWidth: 1200 },
};
