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
  // Con FormData el Content-Type lo pone el navegador, que es el único
  // que conoce el `boundary` del multipart; fijarlo a mano rompe la
  // subida de archivos.
  const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
  const doFetch = () =>
    fetch(`${apiBase()}/api/v1${path}`, {
      ...options,
      headers: {
        ...(isForm ? {} : { "Content-Type": "application/json" }),
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


/**
 * Lista de una respuesta de la API, SIEMPRE como array.
 *
 * El patrón que había repartido por todo el panel era:
 *
 *     const data = await resp.json();
 *     setCosas(data.results || data);
 *
 * y da por hecho que la petición fue bien. Cuando no lo es, el cuerpo
 * sigue siendo JSON válido pero es un objeto —`{"detail": "..."}`—, así
 * que `data.results` es undefined, `|| data` deja el objeto entero en el
 * estado y el `cosas.map(...)` de más abajo lanza «map is not a
 * function». React derriba el árbol y **la pantalla se queda en blanco**:
 * ni el dato, ni un aviso, ni una pista de qué pasó.
 *
 * No es hipotético. El límite de peticiones es de 60 por minuto y por
 * usuario (`DEFAULT_THROTTLE_RATES`), y la pantalla de configuración
 * lanza varias por cada pestaña que se abre: basta con recorrerlas
 * rápido para que la API conteste 429 y el panel se apague. Lo mismo con
 * un 500, un 503 o un 403 con cuerpo.
 *
 * Dos defensas, a propósito:
 *   1. Si la respuesta no es correcta, se lanza un error con el mensaje
 *      del servidor, para que el `catch` de quien llama enseñe algo.
 *   2. Aunque sea correcta, si lo recibido no es una lista se devuelve
 *      una vacía en vez de propagar la sorpresa hasta el `.map`.
 */
export async function readList(resp) {
  if (!resp.ok) throw new Error(await apiErrorMessage(resp));
  const data = await resp.json().catch(() => null);
  const list = data?.results ?? data;
  return Array.isArray(list) ? list : [];
}

/** Igual que `readList`, pero para respuestas que son un único objeto. */
export async function readObject(resp) {
  if (!resp.ok) throw new Error(await apiErrorMessage(resp));
  return resp.json();
}

/**
 * Mensaje legible de una respuesta de error. El backend usa un
 * envoltorio propio (`error.details`) y DRF usa `detail`; los errores de
 * validación llegan como {campo: ["mensaje"]}.
 */
export async function apiErrorMessage(resp) {
  const data = await resp.json().catch(() => null);
  if (resp.status === 429) {
    return "Demasiadas peticiones seguidas. Espera unos segundos y vuelve a intentarlo.";
  }
  const detail = data?.error?.details || data?.detail || data;
  if (!detail) return `No se pudo completar la operación (error ${resp.status}).`;
  if (typeof detail === "string") return detail;
  const first = Object.values(detail)[0];
  const mensaje = Array.isArray(first) ? first[0] : first;
  return typeof mensaje === "string" ? mensaje : `Error ${resp.status}`;
}
