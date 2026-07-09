"use client";

/**
 * Cliente de la API Django.
 * - Detecta la URL del backend: NEXT_PUBLIC_API_URL si está definida;
 *   en Codespaces deriva la URL del puerto 80 desde la del 3000;
 *   en local usa http://localhost.
 * - Maneja JWT: adjunta el access token y lo refresca automáticamente
 *   si expira (un solo reintento por request).
 */

export function apiBase() {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    const { hostname, port, origin } = window.location;
    // Codespaces: algo-3000.app.github.dev → algo-80.app.github.dev
    if (hostname.endsWith(".app.github.dev")) {
      return `https://${hostname.replace("-3000.", "-80.")}`;
    }
    // Dev local con next dev (puerto 3000): la API está en el 80
    if (port === "3000") return "http://localhost";
    // Producción: Nginx sirve panel y API en el mismo origen
    return origin;
  }
  return "http://localhost";
}

const tokens = {
  get access() { return typeof window !== "undefined" ? localStorage.getItem("access") : null; },
  get refresh() { return typeof window !== "undefined" ? localStorage.getItem("refresh") : null; },
  set(access, refresh) {
    localStorage.setItem("access", access);
    if (refresh) localStorage.setItem("refresh", refresh);
  },
  clear() {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
    localStorage.removeItem("user");
  },
};

export function currentUser() {
  if (typeof window === "undefined") return null;
  try { return JSON.parse(localStorage.getItem("user")); } catch { return null; }
}

export async function login(email, password) {
  const resp = await fetch(`${apiBase()}/api/v1/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await resp.json();
  if (!resp.ok) {
    const msg = data?.error?.message || data?.detail || "Credenciales incorrectas.";
    throw new Error(msg);
  }
  tokens.set(data.access, data.refresh);
  // El login devuelve solo tokens; el perfil (nombre y rol) se
  // consulta a /auth/me/ para poder filtrar la navegación por rol.
  const meResp = await fetch(`${apiBase()}/api/v1/auth/me/`, {
    headers: { Authorization: `Bearer ${data.access}` },
  });
  const me = meResp.ok ? await meResp.json() : {};
  localStorage.setItem("user", JSON.stringify(me));
  return data;
}

export function logout() {
  tokens.clear();
  window.location.href = "/login/";
}

async function refreshAccess() {
  if (!tokens.refresh) return false;
  const resp = await fetch(`${apiBase()}/api/v1/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: tokens.refresh }),
  });
  if (!resp.ok) return false;
  const data = await resp.json();
  tokens.set(data.access, data.refresh);
  return true;
}

export async function api(path, options = {}) {
  const doFetch = () =>
    fetch(`${apiBase()}/api/v1${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {}),
        ...(options.headers || {}),
      },
    });

  let resp = await doFetch();
  if (resp.status === 401 && (await refreshAccess())) {
    resp = await doFetch(); // reintento único con el token fresco
  }
  if (resp.status === 401) {
    tokens.clear();
    window.location.href = "/login/";
    throw new Error("Sesión expirada.");
  }
  return resp;
}
