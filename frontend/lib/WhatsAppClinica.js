"use client";

/**
 * Conectar la cuenta de WhatsApp de la clínica.
 *
 * Regla que explica casi todo lo de aquí: **el token entra pero no
 * sale**. El campo nunca se rellena con lo guardado —la API no lo
 * devuelve— y el panel solo sabe si está puesto y cómo acaba. Por eso
 * el campo aparece vacío aunque haya un token guardado, y por eso
 * dejarlo vacío al guardar NO lo borra: para quitarlo hay un botón
 * aparte.
 */

import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "./api";
import { useConfirm } from "./ConfirmDialog";

export default function WhatsAppClinica() {
  const [confirm, ConfirmUI] = useConfirm();
  const [estado, setEstado] = useState(null);
  const [form, setForm] = useState({
    phone_number_id: "", numero_visible: "",
    plantilla_recordatorio: "", access_token: "",
  });
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  const cargar = useCallback(async () => {
    try {
      const resp = await api("/config/whatsapp/");
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      const datos = await resp.json();
      setEstado(datos);
      setForm((f) => ({
        ...f,
        phone_number_id: datos.phone_number_id || "",
        numero_visible: datos.numero_visible || "",
        plantilla_recordatorio: datos.plantilla_recordatorio || "",
        access_token: "",
      }));
    } catch (err) { setError(err.message); }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  async function guardar(e) {
    e.preventDefault();
    setError(""); setAviso("");
    try {
      const cuerpo = { ...form };
      // Vacío significa «no lo toques», no «bórralo».
      if (!cuerpo.access_token.trim()) delete cuerpo.access_token;
      const resp = await api("/config/whatsapp/", {
        method: "PATCH", body: JSON.stringify(cuerpo),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      setAviso("Guardado.");
      cargar();
    } catch (err) { setError(err.message); }
  }

  async function encender(valor) {
    setError(""); setAviso("");
    try {
      const resp = await api("/config/whatsapp/", {
        method: "PATCH", body: JSON.stringify({ activo: valor }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      setAviso(valor ? "Recordatorios encendidos." : "Recordatorios apagados.");
      cargar();
    } catch (err) { setError(err.message); }
  }

  async function borrarToken() {
    const ok = await confirm({
      title: "Quitar el token",
      message: "Los recordatorios dejarán de enviarse hasta que pegues uno nuevo. "
             + "El token no se puede recuperar: habrá que sacarlo otra vez de Meta.",
      confirmLabel: "Quitar", danger: true,
    });
    if (!ok) return;
    try {
      const resp = await api("/config/whatsapp/", {
        method: "PATCH", body: JSON.stringify({ token_borrar: true }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      setAviso("Token quitado. Los recordatorios están apagados.");
      cargar();
    } catch (err) { setError(err.message); }
  }

  if (!estado && !error) return <div className="empty">Cargando…</div>;

  const campo = (k, etiqueta, ayuda, tipo = "text") => (
    <div className="field" style={{ marginBottom: 0 }}>
      <label>{etiqueta}</label>
      <input type={tipo} value={form[k]}
             onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
      {ayuda && <small style={{ color: "var(--ink-soft)", fontSize: 12 }}>{ayuda}</small>}
    </div>
  );

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}
      {aviso && (
        <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>
          ✓ {aviso}
        </div>
      )}

      {estado && (
        <div className="card" style={{ marginBottom: 18,
              background: estado.puede_enviar ? "var(--mint)" : "var(--amber-soft)",
              borderColor: estado.puede_enviar ? "var(--green)" : "var(--amber)" }}>
          <h3 style={{ marginBottom: 6 }}>
            {estado.puede_enviar
              ? "Los recordatorios se están enviando"
              : estado.esta_configurada
                ? "Configurado, pero apagado"
                : "Sin conectar"}
          </h3>
          <p style={{ fontSize: 14, marginBottom: estado.esta_configurada ? 12 : 0 }}>
            {estado.puede_enviar
              ? `Salen desde ${estado.numero_visible || "el número configurado"}.`
              : estado.esta_configurada
                ? "Está todo puesto. Enciéndelo cuando quieras que empiecen a salir."
                : "Pega abajo los datos de tu cuenta de WhatsApp Business."}
          </p>
          {estado.esta_configurada && (
            <button className="btn btn-primary" style={{ fontSize: 13 }}
                    onClick={() => encender(!estado.activo)}>
              {estado.activo ? "Apagar recordatorios" : "Encender recordatorios"}
            </button>
          )}
        </div>
      )}

      <form onSubmit={guardar} className="card" style={{ marginBottom: 18 }}>
        <h3 style={{ marginBottom: 2 }}>Tu cuenta de WhatsApp Business</h3>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", marginBottom: 14 }}>
          Estos datos salen del panel de Meta para desarrolladores, en tu
          aplicación de WhatsApp Business. Los mensajes saldrán del número de
          tu clínica, no del de la plataforma.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
          {campo("phone_number_id", "Identificador de número",
                 "El «Phone number ID» de Meta, no el teléfono.")}
          {campo("numero_visible", "Número tal como lo ve el paciente",
                 "Con código de país: +593999111222")}
          {campo("plantilla_recordatorio", "Plantilla de recordatorio",
                 "El nombre exacto de la plantilla aprobada en Meta.")}
          <div className="field" style={{ marginBottom: 0 }}>
            <label>
              Token de acceso
              {estado?.token_puesto && (
                <span style={{ color: "var(--green)", fontWeight: 400 }}>
                  {" "}· guardado ({estado.token_pista})
                </span>
              )}
            </label>
            <input type="password" value={form.access_token} autoComplete="off"
                   placeholder={estado?.token_puesto ? "Déjalo vacío para conservarlo" : ""}
                   onChange={(e) => setForm({ ...form, access_token: e.target.value })} />
            <small style={{ color: "var(--ink-soft)", fontSize: 12 }}>
              Se guarda cifrado y no se vuelve a mostrar. Dejarlo vacío conserva
              el que ya está.
            </small>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button className="btn btn-primary">Guardar</button>
          {estado?.token_puesto && (
            <button type="button" className="btn btn-ghost"
                    style={{ color: "var(--red)" }} onClick={borrarToken}>
              Quitar el token
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
