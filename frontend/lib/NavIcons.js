"use client";

/**
 * Iconos de línea del menú lateral (Sprint 35).
 * SVG stroke, 24x24, currentColor — heredan el color del texto del nav,
 * así se re-tiñen solos con el tema de la clínica. Trazo redondeado,
 * estilo moderno y consistente entre todos.
 */

const base = {
  width: 20, height: 20, viewBox: "0 0 24 24", fill: "none",
  stroke: "currentColor", strokeWidth: 1.8,
  strokeLinecap: "round", strokeLinejoin: "round",
};

function Inicio(p) {
  return (
    <svg {...base} {...p}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5" />
    </svg>
  );
}

function Pacientes(p) {
  // dos personas
  return (
    <svg {...base} {...p}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
      <path d="M16 5.2a3.2 3.2 0 0 1 0 6" />
      <path d="M17 15.2A5.5 5.5 0 0 1 20.5 20" />
    </svg>
  );
}

function Agenda(p) {
  return (
    <svg {...base} {...p}>
      <rect x="3.5" y="4.5" width="17" height="16" rx="2" />
      <path d="M3.5 9h17M8 3v3M16 3v3" />
      <path d="M7.5 13h3M7.5 16.5h6" />
    </svg>
  );
}

function Firma(p) {
  // pluma
  return (
    <svg {...base} {...p}>
      <path d="M4 20c3-1 4.5-2.5 7.5-7.5l4-4 3.5 3.5-4 4C10 19 8.5 20 4 20Z" />
      <path d="M14 6.5 17.5 10" />
      <path d="M3.5 20.5h6" />
    </svg>
  );
}

function Pagos(p) {
  // tarjeta / billete
  return (
    <svg {...base} {...p}>
      <rect x="2.5" y="5.5" width="19" height="13" rx="2" />
      <path d="M2.5 10h19" />
      <path d="M6 15h3" />
    </svg>
  );
}

function Inventario(p) {
  // caja
  return (
    <svg {...base} {...p}>
      <path d="M12 3 3.5 7v10L12 21l8.5-4V7L12 3Z" />
      <path d="M3.5 7 12 11l8.5-4M12 11v10" />
    </svg>
  );
}

function Reportes(p) {
  // barras
  return (
    <svg {...base} {...p}>
      <path d="M4 20h16" />
      <rect x="6" y="11" width="3" height="6" rx="0.6" />
      <rect x="11" y="7" width="3" height="10" rx="0.6" />
      <rect x="16" y="13" width="3" height="4" rx="0.6" />
    </svg>
  );
}

function Configuracion(p) {
  // engranaje
  return (
    <svg {...base} {...p}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 2.5v2.5M12 19v2.5M4.2 7l2.1 1.2M17.7 15.8l2.1 1.2M4.2 17l2.1-1.2M17.7 8.2l2.1-1.2" />
    </svg>
  );
}

function Plataforma(p) {
  // edificios
  return (
    <svg {...base} {...p}>
      <rect x="3.5" y="8" width="7" height="12" rx="1" />
      <rect x="13" y="4" width="7.5" height="16" rx="1" />
      <path d="M6 11h2M6 14h2M6 17h2M16 7h2M16 10h2M16 13h2M16 16h2" />
    </svg>
  );
}

const ICONS = {
  plataforma: Plataforma,
  inicio: Inicio,
  pacientes: Pacientes,
  agenda: Agenda,
  firma: Firma,
  pagos: Pagos,
  inventario: Inventario,
  reportes: Reportes,
  configuracion: Configuracion,
};

/** Devuelve el componente de icono por clave; fallback a un punto neutro. */
export default function NavIcon({ name, ...props }) {
  const Cmp = ICONS[name];
  if (!Cmp) {
    return (
      <svg {...base} {...props}><circle cx="12" cy="12" r="3" /></svg>
    );
  }
  return <Cmp {...props} />;
}
