"use client";

/**
 * Avisos operativos del día (Sprint 45).
 *
 * Reúne dos señales que hasta ahora había que ir a buscar a mano:
 *  - Pacientes que ya llegaron y aún no son atendidos. El odontólogo ve
 *    los suyos; recepción y administración, los de toda la clínica.
 *  - Cumpleaños de pacientes (hoy y próximos días).
 *
 * Se refresca solo cada minuto: en recepción la pantalla queda abierta
 * horas y un aviso obsoleto es peor que ninguno.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "./api";

export default function DayAlerts({ role }) {
  const [waiting, setWaiting] = useState([]);
  const [birthdays, setBirthdays] = useState([]);

  const load = useCallback(async () => {
    try {
      const [w, b] = await Promise.all([
        api("/appointments/waiting/"),
        api("/patients/birthdays/?days=7"),
      ]);
      if (w.ok) setWaiting(await w.json());
      if (b.ok) setBirthdays(await b.json());
    } catch { /* los avisos son secundarios: nunca rompen el panel */ }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const todayBdays = birthdays.filter((b) => b.is_today);
  const soonBdays = birthdays.filter((b) => !b.is_today);
  if (waiting.length === 0 && birthdays.length === 0) return null;

  return (
    <div style={{ display: "grid", gap: 14,
                  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                  marginBottom: 18 }}>

      {/* Pacientes que ya llegaron */}
      {waiting.length > 0 && (
        <div className="card animate-rise"
             style={{ borderColor: "var(--petrol)", borderWidth: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%",
                           background: "var(--petrol)", flexShrink: 0 }} />
            <h3 style={{ margin: 0, fontSize: 15 }}>
              {role === "doctor" ? "Tus pacientes en sala" : "Pacientes que ya llegaron"}
            </h3>
            <span className="badge badge-warn" style={{ marginLeft: "auto" }}>
              {waiting.length}
            </span>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {waiting.map((w) => (
              <div key={w.id} style={{ display: "flex", alignItems: "center", gap: 10,
                                       fontSize: 13.5, flexWrap: "wrap" }}>
                <a href={`/panel/paciente/?id=${w.patient_id}`} style={{ fontWeight: 600 }}>
                  {w.patient_name}
                </a>
                {role !== "doctor" && (
                  <span style={{ color: "var(--ink-soft)" }}>· {w.doctor_name}</span>
                )}
                <span className="tabular"
                      style={{ marginLeft: "auto", color: w.waiting_minutes >= 15
                        ? "var(--red)" : "var(--ink-soft)", fontSize: 12.5 }}>
                  esperando {w.waiting_minutes} min
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cumpleaños */}
      {birthdays.length > 0 && (
        <div className="card animate-rise">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: 15 }}>Cumpleaños</h3>
            {todayBdays.length > 0 && (
              <span className="badge badge-ok" style={{ marginLeft: "auto" }}>
                {todayBdays.length} hoy
              </span>
            )}
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {birthdays.slice(0, 6).map((b) => (
              <div key={b.id} style={{ display: "flex", alignItems: "center", gap: 10,
                                       fontSize: 13.5, flexWrap: "wrap" }}>
                <a href={`/panel/paciente/?id=${b.id}`}
                   style={{ fontWeight: b.is_today ? 700 : 500 }}>
                  {b.full_name}
                </a>
                <span style={{ color: "var(--ink-soft)", fontSize: 12.5 }}>
                  cumple {b.turns}
                </span>
                <span style={{ marginLeft: "auto", fontSize: 12.5,
                               color: b.is_today ? "var(--green)" : "var(--ink-soft)",
                               fontWeight: b.is_today ? 700 : 400 }}>
                  {b.is_today ? "hoy" : `en ${b.in_days} día${b.in_days === 1 ? "" : "s"}`}
                </span>
              </div>
            ))}
          </div>
          {soonBdays.length > 6 && (
            <p style={{ fontSize: 12, color: "var(--ink-faint)", marginTop: 8 }}>
              y {soonBdays.length - 6} más esta semana
            </p>
          )}
        </div>
      )}
    </div>
  );
}
