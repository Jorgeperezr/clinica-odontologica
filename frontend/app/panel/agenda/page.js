"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "../../../lib/api";

const STATUS_STYLE = {
  pending:     { label: "Pendiente",   cls: "badge-warn" },
  confirmed:   { label: "Confirmada",  cls: "badge-ok" },
  completed:   { label: "Completada",  cls: "badge-ok" },
  cancelled:   { label: "Cancelada",   cls: "badge-danger" },
  rescheduled: { label: "Reagendada",  cls: "badge-warn" },
  no_show:     { label: "No asistió",  cls: "badge-danger" },
};

function todayISO() { return new Date().toISOString().slice(0, 10); }

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" });
}

export default function AgendaPage() {
  const [mode, setMode] = useState("daily");
  const [date, setDate] = useState(todayISO());
  const [doctors, setDoctors] = useState([]);
  const [doctorId, setDoctorId] = useState("");
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ mode, date });
      if (doctorId) params.set("doctor_id", doctorId);
      const resp = await api(`/agenda/view/?${params}`);
      const data = await resp.json();
      setAppointments(data.results || data);
    } catch {
      setError("No se pudo cargar la agenda.");
    } finally {
      setLoading(false);
    }
  }, [mode, date, doctorId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    api("/doctors/").then(async (r) => {
      const data = await r.json();
      setDoctors(data.results || data);
    }).catch(() => {});
  }, []);

  function shiftDate(days) {
    const d = new Date(date + "T12:00:00");
    d.setDate(d.getDate() + days);
    setDate(d.toISOString().slice(0, 10));
  }

  async function doAction(appt, action) {
    try {
      const resp = await api(`/appointments/${appt.id}/${action}/`, { method: "POST" });
      if (!resp.ok) {
        const data = await resp.json();
        throw new Error(data?.error?.message || data?.detail || "No se pudo completar la acción.");
      }
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  const shiftDays = mode === "weekly" ? 7 : 1;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24 }}>Agenda</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cerrar" : "+ Nueva cita"}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}

      {showForm && (
        <AppointmentForm
          doctors={doctors}
          defaultDate={date}
          onSaved={() => { setShowForm(false); load(); }}
        />
      )}

      {/* Controles: día/semana, fecha, doctor */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 18, flexWrap: "wrap" }}>
        <div style={{ display: "flex", border: "1px solid var(--line)", borderRadius: "var(--radius)", overflow: "hidden" }}>
          {["daily", "weekly"].map((m) => (
            <button key={m} onClick={() => setMode(m)}
              style={{
                padding: "8px 16px", border: "none", fontWeight: 600, fontSize: 14,
                background: mode === m ? "var(--petrol)" : "#fff",
                color: mode === m ? "#fff" : "var(--ink)",
              }}>
              {m === "daily" ? "Día" : "Semana"}
            </button>
          ))}
        </div>

        <button className="btn btn-ghost" onClick={() => shiftDate(-shiftDays)} aria-label="Anterior">←</button>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)}
               style={{ padding: "8px 10px", border: "1px solid var(--line)", borderRadius: "var(--radius)" }} />
        <button className="btn btn-ghost" onClick={() => shiftDate(shiftDays)} aria-label="Siguiente">→</button>
        <button className="btn btn-ghost" onClick={() => setDate(todayISO())}>Hoy</button>

        <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}
                style={{ padding: "8px 10px", border: "1px solid var(--line)", borderRadius: "var(--radius)", marginLeft: "auto" }}>
          <option value="">Todos los doctores</option>
          {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </select>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty">Cargando…</div>
        ) : appointments.length === 0 ? (
          <div className="empty">No hay citas en este período. Agenda la primera con “+ Nueva cita”.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Hora</th>
                {mode === "weekly" && <th>Fecha</th>}
                <th>Paciente</th>
                <th>Doctor</th>
                <th>Estado</th>
                <th style={{ textAlign: "right" }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((a) => {
                const st = STATUS_STYLE[a.status] || { label: a.status, cls: "badge-warn" };
                return (
                  <tr key={a.id}>
                    <td className="tabular" style={{ whiteSpace: "nowrap" }}>
                      {fmtTime(a.scheduled_start)}–{fmtTime(a.scheduled_end)}
                    </td>
                    {mode === "weekly" && (
                      <td className="tabular">{a.scheduled_start.slice(0, 10)}</td>
                    )}
                    <td style={{ fontWeight: 600 }}>{a.patient_name}</td>
                    <td>{a.doctor_name}</td>
                    <td><span className={`badge ${st.cls}`}>{st.label}</span></td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <RowActions appt={a} onAction={doAction} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function RowActions({ appt, onAction }) {
  const btn = { padding: "5px 10px", fontSize: 12, borderRadius: 7, marginLeft: 6 };
  if (appt.status === "pending") {
    return (
      <>
        <button className="btn btn-ghost" style={btn} onClick={() => onAction(appt, "confirm")}>Confirmar</button>
        <button className="btn btn-ghost" style={btn} onClick={() => onAction(appt, "cancel")}>Cancelar</button>
      </>
    );
  }
  if (appt.status === "confirmed" && !appt.checkin_at) {
    return (
      <>
        <button className="btn btn-primary" style={btn} onClick={() => onAction(appt, "checkin")}>Llegó</button>
        <button className="btn btn-ghost" style={btn} onClick={() => onAction(appt, "cancel")}>Cancelar</button>
      </>
    );
  }
  if (appt.checkin_at && !appt.checkout_at) {
    return <button className="btn btn-primary" style={btn} onClick={() => onAction(appt, "checkout")}>Finalizar</button>;
  }
  return null;
}

function AppointmentForm({ doctors, defaultDate, onSaved }) {
  const [patientQuery, setPatientQuery] = useState("");
  const [patientResults, setPatientResults] = useState([]);
  const [patient, setPatient] = useState(null);
  const [doctor, setDoctor] = useState("");
  const [date, setDate] = useState(defaultDate);
  const [start, setStart] = useState("09:00");
  const [end, setEnd] = useState("09:30");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [delinquent, setDelinquent] = useState(false);
  const [saving, setSaving] = useState(false);

  async function searchPatients(q) {
    setPatientQuery(q);
    setPatient(null);
    if (q.length < 2) { setPatientResults([]); return; }
    try {
      const resp = await api(`/patients/?search=${encodeURIComponent(q)}`);
      const data = await resp.json();
      setPatientResults((data.results || data).slice(0, 6));
    } catch { /* silencioso */ }
  }

  async function submit(withOverride = false) {
    if (!patient) { setError("Selecciona un paciente de la lista."); return; }
    setError("");
    setSaving(true);
    setDelinquent(false);
    try {
      const body = {
        patient: patient.id,
        doctor,
        scheduled_start: `${date}T${start}:00`,
        scheduled_end: `${date}T${end}:00`,
        notes,
      };
      if (withOverride) body.override = "true";
      const resp = await api("/appointments/", { method: "POST", body: JSON.stringify(body) });
      const data = await resp.json();
      if (resp.status === 409 && data?.error?.code === "patient_delinquent") {
        setDelinquent(true);
        return;
      }
      if (!resp.ok) {
        const detail = data?.error?.details || data?.error?.message || data;
        const first = typeof detail === "object" ? Object.values(detail)[0] : detail;
        throw new Error(Array.isArray(first) ? first[0] : String(first));
      }
      onSaved();
    } catch (err) {
      setError(err.message || "No se pudo agendar la cita.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginBottom: 14 }}>Nueva cita</h3>
      {error && <div className="error-box">{error}</div>}

      {delinquent && (
        <div className="error-box" style={{ background: "var(--amber-soft)", color: "var(--amber)" }}>
          <strong>Paciente con cuotas vencidas.</strong> El sistema bloquea el
          agendamiento por morosidad. ¿Agendar de todas formas (excepción manual)?
          <div style={{ marginTop: 10 }}>
            <button className="btn btn-primary" style={{ fontSize: 13 }} onClick={() => submit(true)} disabled={saving}>
              Sí, agendar con excepción
            </button>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 16px" }}>
        <div className="field" style={{ position: "relative" }}>
          <label>Paciente *</label>
          <input
            placeholder="Buscar por nombre o cédula…"
            value={patient ? `${patient.full_name} (${patient.national_id})` : patientQuery}
            onChange={(e) => searchPatients(e.target.value)}
          />
          {patientResults.length > 0 && !patient && (
            <div style={{
              position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
              background: "#fff", border: "1px solid var(--line)", borderRadius: 8,
              boxShadow: "0 6px 18px rgba(0,0,0,.08)",
            }}>
              {patientResults.map((p) => (
                <div key={p.id}
                     onClick={() => { setPatient(p); setPatientResults([]); }}
                     style={{ padding: "9px 12px", cursor: "pointer", fontSize: 14 }}>
                  <strong>{p.full_name}</strong> · <span className="tabular">{p.national_id}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="field">
          <label>Doctor *</label>
          <select required value={doctor} onChange={(e) => setDoctor(e.target.value)}>
            <option value="">Seleccionar…</option>
            {doctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
          </select>
        </div>

        <div className="field">
          <label>Fecha *</label>
          <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        <div className="field" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <label>Inicio *</label>
            <input type="time" required value={start} onChange={(e) => setStart(e.target.value)} style={{ width: "100%" }} />
          </div>
          <div>
            <label>Fin *</label>
            <input type="time" required value={end} onChange={(e) => setEnd(e.target.value)} style={{ width: "100%" }} />
          </div>
        </div>
      </div>

      <div className="field">
        <label>Notas</label>
        <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>

      <button className="btn btn-primary" disabled={saving || !patient || !doctor} onClick={() => submit(false)}>
        {saving ? "Agendando…" : "Agendar cita"}
      </button>
    </div>
  );
}
