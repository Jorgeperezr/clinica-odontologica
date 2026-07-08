"use client";

import { useEffect, useState } from "react";
import { api, currentUser } from "../../lib/api";

export default function Dashboard() {
  const [user, setUser] = useState(null);

  useEffect(() => { setUser(currentUser()); }, []);

  if (!user) return null;

  return (
    <div>
      <h1 style={{ fontSize: 24, marginBottom: 6 }}>
        Hola, {user.first_name || user.email}
      </h1>
      <p style={{ color: "var(--ink-soft)", marginBottom: 24 }}>
        Bienvenido al panel de gestión de la clínica.
      </p>

      <div className="card">
        <h3 style={{ marginBottom: 8 }}>Estado del sistema</h3>
        <p style={{ fontSize: 14, color: "var(--ink-soft)" }}>
          El backend está completo (11 módulos). Los módulos del panel se
          activan sprint a sprint: Pacientes ya está disponible en la barra
          lateral; Agenda, Pagos e Inventario llegan en los próximos sprints.
        </p>
      </div>
    </div>
  );
}
