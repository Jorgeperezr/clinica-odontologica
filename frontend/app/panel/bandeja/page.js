"use client";

/**
 * Bandeja de la app: lo que los pacientes piden desde la aplicación.
 *
 *   · Solicitudes de cita: se agendan creando la cita de verdad (con las
 *     mismas validaciones que la agenda, incluida la morosidad) o se
 *     rechazan con una explicación, que el paciente lee en la app.
 *   · Mensajes: se contestan aquí y la respuesta aparece en la app.
 *
 * Quién puede hacer qué lo deciden las funciones de cada profesional
 * («Gestionar la agenda», «Responder mensajes de la app»). Aquí solo se
 * esconden los botones; quien de verdad lo impide es la API.
 */

import { useCallback, useEffect, useState } from "react";

import { api, currentUser, readList, tieneFuncion } from "../../../lib/api";

const HORA_POR_FRANJA = { manana: "09:00", tarde: "15:00", cualquiera: "10:00" };

function fecha(iso) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("es-EC", { weekday: "short", day: "numeric", month: "short" });
}

function hace(iso) {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 60) return `hace ${Math.max(1, min)} min`;
  if (min < 60 * 24) return `hace ${Math.round(min / 60)} h`;
  return `hace ${Math.round(min / 1440)} d`;
}

function sumarMinutos(hhmm, minutos) {
  const [h, m] = hhmm.split(":").map(Number);
  const total = h * 60 + m + minutos;
  return `${String(Math.floor(total / 60) % 24).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

async function error(resp, porDefecto) {
  const d = await resp.json().catch(() => null);
  const det = d?.error?.details || d?.error?.message || d?.detail || d;
  if (typeof det === "string") return det;
  const primero = det && typeof det === "object" ? Object.values(det)[0] : null;
  return Array.isArray(primero) ? primero[0] : (primero || porDefecto);
}

/* ── Una solicitud de cita ── */
function Solicitud({ s, doctores, puedeAgendar, onHecho }) {
  const [modo, setModo] = useState(null);   // null | "agendar" | "rechazar"
  const [form, setForm] = useState({
    doctor: doctores[0]?.id || "", dia: s.fecha_preferida,
    hora: HORA_POR_FRANJA[s.franja] || "10:00", minutos: 30, respuesta: "",
  });
  const [moroso, setMoroso] = useState(false);
  const [msg, setMsg] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!form.doctor && doctores[0]) setForm((f) => ({ ...f, doctor: doctores[0].id }));
  }, [doctores, form.doctor]);

  async function agendar(forzar = false) {
    setMsg(""); setEnviando(true); setMoroso(false);
    try {
      const cuerpo = {
        doctor: form.doctor,
        // Hora local de la clínica, igual que la agenda.
        scheduled_start: `${form.dia}T${form.hora}:00`,
        scheduled_end: `${form.dia}T${sumarMinutos(form.hora, Number(form.minutos))}:00`,
        respuesta: form.respuesta,
      };
      if (forzar) cuerpo.override = true;
      const r = await api(`/bandeja-app/solicitudes/${s.id}/agendar/`, { method: "POST", body: JSON.stringify(cuerpo) });
      if (r.status === 409) {
        const d = await r.json().catch(() => null);
        if (d?.error?.code === "patient_delinquent") { setMoroso(true); return; }
        throw new Error(d?.detail || "Esa solicitud ya se atendió.");
      }
      if (!r.ok) throw new Error(await error(r, `No se pudo agendar (error ${r.status}).`));
      onHecho("Cita creada. El paciente ya la ve en la app.");
    } catch (e) { setMsg(e.message); } finally { setEnviando(false); }
  }

  async function rechazar() {
    setMsg(""); setEnviando(true);
    try {
      const r = await api(`/bandeja-app/solicitudes/${s.id}/rechazar/`, {
        method: "POST", body: JSON.stringify({ respuesta: form.respuesta }),
      });
      if (!r.ok) throw new Error(await error(r, `No se pudo responder (error ${r.status}).`));
      onHecho("Respuesta enviada al paciente.");
    } catch (e) { setMsg(e.message); } finally { setEnviando(false); }
  }

  const atendida = s.estado !== "pendiente";
  return (
    <div className="card" style={{ marginBottom: 10, padding: "12px 14px" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
        <strong>{s.paciente.nombre}</strong>
        {s.paciente.telefono && <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>{s.paciente.telefono}</span>}
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--ink-faint)" }}>{hace(s.creada)}</span>
      </div>
      <div style={{ fontSize: 13.5, marginTop: 4 }}>
        Prefiere el <strong>{fecha(s.fecha_preferida)}</strong>, {s.franja_texto.toLowerCase()}
        {s.motivo && <span style={{ color: "var(--ink-soft)" }}> · «{s.motivo}»</span>}
      </div>
      {atendida && (
        <div style={{ fontSize: 12.5, marginTop: 6 }}>
          <span className={`badge ${s.estado === "agendada" ? "badge-ok" : "badge-warn"}`}>{s.estado_texto}</span>
          {s.cita && <span style={{ marginLeft: 8 }}>{new Date(s.cita.inicio).toLocaleString("es-EC", { dateStyle: "medium", timeStyle: "short" })}</span>}
          {s.respuesta && <span style={{ marginLeft: 8, color: "var(--ink-soft)" }}>«{s.respuesta}»</span>}
        </div>
      )}

      {!atendida && puedeAgendar && modo === null && (
        <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
          <button type="button" className="btn btn-primary" style={{ fontSize: 12.5 }} onClick={() => setModo("agendar")}>Agendar</button>
          <button type="button" className="btn btn-ghost" style={{ fontSize: 12.5 }} onClick={() => setModo("rechazar")}>No se puede</button>
        </div>
      )}

      {modo === "agendar" && (
        <div style={{ marginTop: 10, display: "grid", gap: 8, gridTemplateColumns: "1.4fr 1fr .8fr .8fr", alignItems: "end" }}>
          <div className="field" style={{ margin: 0 }}><label>Doctor/a</label>
            <select value={form.doctor} onChange={(e) => setForm({ ...form, doctor: e.target.value })}>
              {doctores.map((d) => <option key={d.id} value={d.id}>{d.full_name || d.email}</option>)}
            </select></div>
          <div className="field" style={{ margin: 0 }}><label>Día</label>
            <input type="date" value={form.dia} onChange={(e) => setForm({ ...form, dia: e.target.value })} /></div>
          <div className="field" style={{ margin: 0 }}><label>Hora</label>
            <input type="time" value={form.hora} onChange={(e) => setForm({ ...form, hora: e.target.value })} /></div>
          <div className="field" style={{ margin: 0 }}><label>Duración</label>
            <select value={form.minutos} onChange={(e) => setForm({ ...form, minutos: e.target.value })}>
              {[15, 30, 45, 60, 90].map((m) => <option key={m} value={m}>{m} min</option>)}
            </select></div>
          <div className="field" style={{ margin: 0, gridColumn: "1 / -1" }}>
            <label>Mensaje para el paciente (opcional)</label>
            <input value={form.respuesta} maxLength={300} placeholder="Ej.: Te esperamos 10 minutos antes."
                   onChange={(e) => setForm({ ...form, respuesta: e.target.value })} /></div>
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: 6 }}>
            <button type="button" className="btn btn-primary" disabled={enviando || !form.doctor}
                    onClick={() => agendar(false)}>{enviando ? "Agendando…" : "Crear cita"}</button>
            <button type="button" className="btn btn-ghost" onClick={() => { setModo(null); setMoroso(false); }}>Cancelar</button>
          </div>
        </div>
      )}

      {moroso && (
        <div className="error-box" style={{ marginTop: 10 }}>
          Este paciente tiene cuotas vencidas: la agenda no le da cita sin más.
          <button type="button" className="btn btn-ghost" style={{ marginLeft: 10, fontSize: 12.5 }}
                  onClick={() => agendar(true)}>Agendar de todas formas</button>
        </div>
      )}

      {modo === "rechazar" && (
        <div style={{ marginTop: 10 }}>
          <div className="field" style={{ margin: 0 }}>
            <label>Explícale al paciente por qué (obligatorio)</label>
            <input value={form.respuesta} maxLength={300} autoFocus
                   placeholder="Ej.: Esa semana no hay agenda; llámanos para buscar otro día."
                   onChange={(e) => setForm({ ...form, respuesta: e.target.value })} />
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            <button type="button" className="btn btn-primary" disabled={enviando || !form.respuesta.trim()}
                    onClick={rechazar}>Enviar respuesta</button>
            <button type="button" className="btn btn-ghost" onClick={() => setModo(null)}>Cancelar</button>
          </div>
        </div>
      )}
      {msg && <div className="error-box" style={{ marginTop: 8 }}>{msg}</div>}
    </div>
  );
}

/* ── Un mensaje ── */
function Mensaje({ m, puedeResponder, onHecho }) {
  const [texto, setTexto] = useState("");
  const [msg, setMsg] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function responder() {
    setMsg(""); setEnviando(true);
    try {
      const r = await api(`/bandeja-app/mensajes/${m.id}/responder/`, {
        method: "POST", body: JSON.stringify({ respuesta: texto }),
      });
      if (!r.ok) throw new Error(await error(r, `No se pudo responder (error ${r.status}).`));
      onHecho("Respuesta enviada. El paciente la ve en la app.");
    } catch (e) { setMsg(e.message); } finally { setEnviando(false); }
  }

  return (
    <div className="card" style={{ marginBottom: 10, padding: "12px 14px" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
        <strong>{m.paciente.nombre}</strong>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--ink-faint)" }}>{hace(m.creado)}</span>
      </div>
      <p style={{ margin: "6px 0 0", fontSize: 14, whiteSpace: "pre-wrap" }}>{m.texto}</p>
      {m.respondido ? (
        <p style={{ margin: "8px 0 0", fontSize: 13.5, color: "var(--ink-soft)", borderLeft: "3px solid var(--petrol)", paddingLeft: 10, whiteSpace: "pre-wrap" }}>
          {m.respuesta}
          <span style={{ display: "block", fontSize: 11.5, color: "var(--ink-faint)" }}>
            {m.respondido_por || "Clínica"} · {hace(m.respondido)}
          </span>
        </p>
      ) : puedeResponder && (
        <div style={{ marginTop: 10 }}>
          <textarea rows={2} value={texto} maxLength={1000} placeholder="Escribe la respuesta…"
                    onChange={(e) => setTexto(e.target.value)} style={{ width: "100%" }} />
          <button type="button" className="btn btn-primary" style={{ marginTop: 6, fontSize: 12.5 }}
                  disabled={enviando || !texto.trim()} onClick={responder}>
            {enviando ? "Enviando…" : "Responder"}
          </button>
        </div>
      )}
      {msg && <div className="error-box" style={{ marginTop: 8 }}>{msg}</div>}
    </div>
  );
}

export default function BandejaPage() {
  const [solicitudes, setSolicitudes] = useState(null);
  const [mensajes, setMensajes] = useState(null);
  const [doctores, setDoctores] = useState([]);
  const [historial, setHistorial] = useState(false);
  const [ok, setOk] = useState("");
  const [err, setErr] = useState("");
  const [permisos, setPermisos] = useState({ agendar: false, responder: false });

  const cargar = useCallback(async () => {
    setErr("");
    try {
      const [rs, rm] = await Promise.all([
        api(`/bandeja-app/solicitudes/?estado=${historial ? "todas" : "pendiente"}`),
        api(`/bandeja-app/mensajes/?pendientes=${historial ? "0" : "1"}`),
      ]);
      if (rs.status === 403 || rm.status === 403) {
        throw new Error("Tu clínica no tiene activada la app del paciente, o no tienes acceso a esta bandeja.");
      }
      setSolicitudes(await readList(rs));
      setMensajes(await readList(rm));
      // Para el contador del menú.
      window.dispatchEvent(new Event("bandeja-actualizada"));
    } catch (e) { setErr(e.message); }
  }, [historial]);

  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    const u = currentUser();
    setPermisos({ agendar: tieneFuncion(u, "agenda"), responder: tieneFuncion(u, "mensajes_app") });
    api("/doctors/").then(readList).then(setDoctores).catch(() => {});
  }, []);

  function hecho(texto) { setOk(texto); cargar(); }

  return (
    <div style={{ maxWidth: 1100 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 24, marginBottom: 4 }}>Bandeja de la app</h1>
        <label style={{ marginLeft: "auto", fontSize: 13, display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={historial} onChange={(e) => setHistorial(e.target.checked)} />
          Ver también lo ya atendido
        </label>
      </div>
      <p style={{ color: "var(--ink-soft)", marginBottom: 16, fontSize: 14 }}>
        Lo que los pacientes piden desde la aplicación. Lo más antiguo, primero.
      </p>
      {err && <div className="error-box">{err}</div>}
      {ok && <div className="success-box">✓ {ok}</div>}

      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", alignItems: "start" }}>
        <section>
          <h2 style={{ fontSize: 16, marginBottom: 10 }}>
            Solicitudes de cita {solicitudes && <span className="badge">{solicitudes.filter((s) => s.estado === "pendiente").length}</span>}
          </h2>
          {solicitudes === null && !err && <div className="skeleton" style={{ height: 90 }} />}
          {solicitudes?.length === 0 && <div className="card"><div className="empty">No hay solicitudes pendientes.</div></div>}
          {solicitudes?.map((s) => (
            <Solicitud key={s.id} s={s} doctores={doctores} puedeAgendar={permisos.agendar} onHecho={hecho} />
          ))}
        </section>
        <section>
          <h2 style={{ fontSize: 16, marginBottom: 10 }}>
            Mensajes {mensajes && <span className="badge">{mensajes.filter((m) => !m.respondido).length}</span>}
          </h2>
          {mensajes === null && !err && <div className="skeleton" style={{ height: 90 }} />}
          {mensajes?.length === 0 && <div className="card"><div className="empty">No hay mensajes sin responder.</div></div>}
          {mensajes?.map((m) => (
            <Mensaje key={m.id} m={m} puedeResponder={permisos.responder} onHecho={hecho} />
          ))}
        </section>
      </div>
    </div>
  );
}
