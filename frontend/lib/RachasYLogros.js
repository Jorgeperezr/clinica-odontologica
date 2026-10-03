"use client";

/**
 * Rachas y logros de la clínica.
 *
 * Dos mitades, porque son dos actos distintos: definir QUÉ se premia
 * —el catálogo— y decidir A QUIÉN se premia hoy.
 *
 * El beneficio es informativo y la pantalla lo dice: el descuento NO se
 * aplica solo al presupuestar, lo aplica una persona. Callarlo haría que
 * la clínica prometiera en la app algo que la recepción no sabe que
 * existe, y eso se descubre discutiendo con un paciente en el mostrador.
 */

import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage, readList } from "./api";
import { useConfirm } from "./ConfirmDialog";

const ICONOS = [
  ["estrella", "★ Estrella"], ["racha", "🔥 Racha"], ["diente", "🦷 Diente"],
  ["corazon", "♥ Corazón"], ["escudo", "🛡 Escudo"], ["regalo", "🎁 Regalo"],
];

const REGLAS = [
  ["manual", "La otorga una persona"],
  ["asistencia_mensual", "Asistió a sus citas del mes"],
  ["al_dia_pagos", "Cerró el mes sin cuotas vencidas"],
];

const VACIO = {
  nombre: "", descripcion: "", icono: "estrella", beneficio: "",
  regla: "manual", meses_requeridos: 1, activo: true,
};

export default function RachasYLogros() {
  const [confirm, ConfirmUI] = useConfirm();
  const [logros, setLogros] = useState([]);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [otorgandoA, setOtorgandoA] = useState(null);

  const cargar = useCallback(async () => {
    try {
      setLogros(await readList(await api("/logros/")));
    } catch (err) {
      setError(err?.message || "No se pudieron cargar los logros.");
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const actual = editando || form;
  const cambiar = (k, v) =>
    editando ? setEditando({ ...editando, [k]: v }) : setForm({ ...form, [k]: v });

  async function guardar(e) {
    e.preventDefault();
    setError(""); setAviso("");
    try {
      const ruta = editando ? `/logros/${editando.id}/` : "/logros/";
      const resp = await api(ruta, {
        method: editando ? "PATCH" : "POST",
        body: JSON.stringify(actual),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      setForm(VACIO); setEditando(null);
      setAviso(editando ? "Logro actualizado." : `Logro «${actual.nombre}» creado.`);
      cargar();
    } catch (err) { setError(err.message); }
  }

  async function borrar(logro) {
    const concedido = logro.concedidos > 0;
    const ok = await confirm({
      title: concedido ? `Desactivar «${logro.nombre}»` : `Eliminar «${logro.nombre}»`,
      message: concedido
        ? `Ya se concedió ${logro.concedidos} vez/veces, así que no se borra: se desactiva. `
          + "Borrarlo reescribiría la historia de quien lo ganó."
        : "Todavía no lo tiene nadie, así que se elimina del catálogo.",
      confirmLabel: concedido ? "Desactivar" : "Eliminar",
      danger: true,
    });
    if (!ok) return;
    try {
      const resp = await api(`/logros/${logro.id}/`, { method: "DELETE" });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      cargar();
    } catch (err) { setError(err.message); }
  }

  async function evaluar() {
    setError(""); setAviso("");
    try {
      const resp = await api("/logros/evaluar/", { method: "POST" });
      const datos = await resp.json();
      if (!resp.ok) throw new Error(datos?.detail || `Error ${resp.status}`);
      setAviso(datos.detalle);
      cargar();
    } catch (err) { setError(err.message); }
  }

  const automatico = actual.regla !== "manual";

  return (
    <div>
      {ConfirmUI}
      {error && <div className="error-box">{error}</div>}
      {aviso && (
        <div className="error-box" style={{ background: "var(--mint)", color: "var(--petrol-deep)" }}>
          ✓ {aviso}
        </div>
      )}

      <div className="card" style={{ marginBottom: 18, background: "var(--amber-soft)",
                                     borderColor: "var(--amber)" }}>
        <strong>El beneficio es informativo.</strong>{" "}
        El paciente lo ve en su app, pero el descuento <strong>no se aplica solo</strong>
        {" "}al presupuestar: lo aplica quien atiende. Se hizo así para no tocar la
        precedencia de precios (tarifario pactado → convenio → general → catálogo)
        con una regla que nadie ha visto funcionar todavía.
      </div>

      <form onSubmit={guardar} className="card"
            style={{ marginBottom: 18, ...(editando ? { borderColor: "var(--petrol)" } : {}) }}>
        <h3 style={{ marginBottom: 12 }}>
          {editando ? `Editar — ${editando.nombre}` : "Nuevo logro"}
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr 1.4fr", gap: "12px 14px" }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Nombre *</label>
            <input required maxLength={80} value={actual.nombre}
                   onChange={(e) => cambiar("nombre", e.target.value)} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Icono</label>
            <select value={actual.icono} onChange={(e) => cambiar("icono", e.target.value)}>
              {ICONOS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Cómo se gana</label>
            <select value={actual.regla} onChange={(e) => cambiar("regla", e.target.value)}>
              {REGLAS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select></div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 14px", marginTop: 12 }}>
          <div className="field" style={{ marginBottom: 0 }}><label>Descripción</label>
            <input maxLength={200} value={actual.descripcion}
                   placeholder="Lo que el paciente lee en la app"
                   onChange={(e) => cambiar("descripcion", e.target.value)} /></div>
          <div className="field" style={{ marginBottom: 0 }}><label>Beneficio</label>
            <input maxLength={200} value={actual.beneficio}
                   placeholder="10% de descuento en tu próxima profilaxis"
                   onChange={(e) => cambiar("beneficio", e.target.value)} /></div>
        </div>
        {automatico && (
          <div style={{ display: "flex", gap: 14, alignItems: "end", marginTop: 12 }}>
            <div className="field" style={{ marginBottom: 0, width: 200 }}>
              <label>Meses seguidos que hacen falta</label>
              <input type="number" min={1} max={36} value={actual.meses_requeridos}
                     onChange={(e) => cambiar("meses_requeridos", Number(e.target.value))} />
            </div>
            <span style={{ fontSize: 12, color: "var(--ink-soft)", paddingBottom: 8 }}>
              Con 1 se premia el primer mes que se cumpla. Con 3 o más, es una racha.
            </span>
          </div>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button className="btn btn-primary">{editando ? "Guardar cambios" : "Crear logro"}</button>
          {editando && (
            <button type="button" className="btn btn-ghost"
                    onClick={() => setEditando(null)}>Cancelar</button>
          )}
        </div>
      </form>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        <h3>Catálogo</h3>
        <button className="btn btn-ghost" style={{ fontSize: 13 }} onClick={evaluar}>
          ⟳ Evaluar reglas automáticas
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {logros.length === 0 ? (
          <div className="empty">
            Sin logros todavía. Crea el primero arriba: por ejemplo «Constancia»,
            que se gana asistiendo a las citas del mes.
          </div>
        ) : (
          <table>
            <thead>
              <tr><th>Logro</th><th>Cómo se gana</th><th>Beneficio</th>
                  <th>Concedido</th><th>Estado</th><th></th></tr>
            </thead>
            <tbody>
              {logros.map((l) => (
                <tr key={l.id} style={l.activo ? {} : { opacity: 0.6 }}>
                  <td>
                    <strong>{l.nombre}</strong>
                    {l.descripcion && (
                      <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{l.descripcion}</div>
                    )}
                  </td>
                  <td style={{ fontSize: 13 }}>
                    {l.regla_display}
                    {l.es_automatico && l.meses_requeridos > 1 && (
                      <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                        {l.meses_requeridos} meses seguidos
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: 13 }}>{l.beneficio || "—"}</td>
                  <td className="tabular">{l.concedidos}</td>
                  <td>{l.activo
                    ? <span className="badge badge-ok">Activo</span>
                    : <span className="badge badge-danger">Desactivado</span>}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {!l.es_automatico && l.activo && (
                      <button className="btn btn-primary" style={{ padding: "4px 10px", fontSize: 12 }}
                              onClick={() => setOtorgandoA(l)}>Otorgar</button>
                    )}
                    <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6 }}
                            onClick={() => setEditando({ ...l })}>Editar</button>
                    <button className="btn btn-ghost"
                            style={{ padding: "4px 10px", fontSize: 12, marginLeft: 6, color: "var(--red)" }}
                            onClick={() => borrar(l)}>
                      {l.concedidos > 0 ? "Desactivar" : "Eliminar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {otorgandoA && (
        <Otorgar logro={otorgandoA}
                 onCerrar={() => setOtorgandoA(null)}
                 onHecho={(msg) => { setOtorgandoA(null); setAviso(msg); cargar(); }} />
      )}
    </div>
  );
}

/**
 * El nombre del paciente, venga como venga.
 *
 * El LISTADO (`PatientListSerializer`) manda `full_name`, y el detalle
 * manda `first_name`/`last_name`. Dar por hecho el segundo en la
 * búsqueda dejaba «concedido a undefined undefined» en el aviso de
 * éxito, que es de las cosas que solo se ven recorriendo la pantalla.
 */
function nombreDe(p) {
  const compuesto = `${p.first_name || ""} ${p.last_name || ""}`.trim();
  return (p.full_name || "").trim() || compuesto || "el paciente";
}

/** Elegir a quién se le concede un logro manual. */
function Otorgar({ logro, onCerrar, onHecho }) {
  const [busqueda, setBusqueda] = useState("");
  const [pacientes, setPacientes] = useState([]);
  const [error, setError] = useState("");
  const [nota, setNota] = useState("");

  useEffect(() => {
    const id = setTimeout(async () => {
      if (busqueda.trim().length < 2) { setPacientes([]); return; }
      try {
        setPacientes(await readList(
          await api(`/patients/?search=${encodeURIComponent(busqueda.trim())}`)));
      } catch { setPacientes([]); }
    }, 300);   // sin esto se lanza una petición por tecla y salta el 429
    return () => clearTimeout(id);
  }, [busqueda]);

  async function otorgar(paciente) {
    setError("");
    try {
      const resp = await api("/logros/otorgar/", {
        method: "POST",
        body: JSON.stringify({ logro: logro.id, patient: paciente.id, nota }),
      });
      if (!resp.ok) throw new Error(await apiErrorMessage(resp));
      onHecho(`«${logro.nombre}» concedido a ${nombreDe(paciente)}.`);
    } catch (err) { setError(err.message); }
  }

  return (
    <div className="card" style={{ marginTop: 18, borderColor: "var(--petrol)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
        <h3>Otorgar «{logro.nombre}»</h3>
        <button className="btn btn-ghost" style={{ padding: "4px 12px", fontSize: 12 }}
                onClick={onCerrar}>✕</button>
      </div>
      {error && <div className="error-box">{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1.5fr", gap: 14 }}>
        <div className="field" style={{ marginBottom: 0 }}><label>Buscar paciente</label>
          <input value={busqueda} autoFocus placeholder="Nombre o cédula"
                 onChange={(e) => setBusqueda(e.target.value)} /></div>
        <div className="field" style={{ marginBottom: 0 }}><label>Nota (opcional)</label>
          <input value={nota} maxLength={200} placeholder="Por qué se le premia"
                 onChange={(e) => setNota(e.target.value)} /></div>
      </div>
      {busqueda.trim().length >= 2 && (
        <div style={{ marginTop: 12 }}>
          {pacientes.length === 0 ? (
            <div className="empty" style={{ padding: 14 }}>Sin coincidencias.</div>
          ) : pacientes.slice(0, 8).map((p) => (
            <div key={p.id} style={{ display: "flex", justifyContent: "space-between",
                                     alignItems: "center", padding: "8px 0",
                                     borderBottom: "1px solid var(--line)" }}>
              <span>{nombreDe(p)}
                <span style={{ color: "var(--ink-soft)", fontSize: 12 }}>
                  {p.national_id ? ` · ${p.national_id}` : ""}
                </span>
              </span>
              <button className="btn btn-primary" style={{ padding: "4px 12px", fontSize: 12 }}
                      onClick={() => otorgar(p)}>Otorgar</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
