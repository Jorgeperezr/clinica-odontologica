"use client";

/**
 * Literal K del formulario MSP 033 — Simbología del Odontograma.
 * Reemplaza la leyenda simple (cuadros de color) por los símbolos
 * oficiales del formulario, mapeados por código de estado. La lógica de
 * los estados no cambia: esto es solo la representación gráfica de cada
 * uno, tomada del catálogo (states) que ya viene del backend.
 */

// Símbolo SVG oficial por código de estado (18x18)
function Symbol({ code, color }) {
  const s = 18, c = color || "#111827";
  const wrap = (child) => (
    <svg width={s} height={s} viewBox="0 0 18 18" style={{ flexShrink: 0 }}>{child}</svg>
  );
  switch (code) {
    case "CARIES":               // círculo rojo relleno
      return wrap(<circle cx="9" cy="9" r="6" fill="#c62828" />);
    case "OBTURADO":             // círculo azul relleno
      return wrap(<circle cx="9" cy="9" r="6" fill="#1565c0" />);
    case "SELLANTE_NECESARIO":   // asterisco rojo
      return wrap(<text x="9" y="14" textAnchor="middle" fontSize="16" fill="#c62828">✱</text>);
    case "SELLANTE":             // asterisco azul
      return wrap(<text x="9" y="14" textAnchor="middle" fontSize="16" fill="#1565c0">✱</text>);
    case "INDICADA_EXTRACCION":  // X roja
      return wrap(<text x="9" y="14" textAnchor="middle" fontSize="15" fontWeight="700" fill="#c62828">✕</text>);
    case "PERDIDA_CARIES":       // X azul
      return wrap(<text x="9" y="14" textAnchor="middle" fontSize="15" fontWeight="700" fill="#1565c0">✕</text>);
    case "PERDIDA_OTRA":         // círculo con X (pérdida otra causa)
      return wrap(<><circle cx="9" cy="9" r="7" fill="none" stroke="#111827" strokeWidth="1.3" /><path d="M4 4 L14 14 M14 4 L4 14" stroke="#111827" strokeWidth="1.3" /></>);
    case "AUSENTE":              // letra A
      return wrap(<text x="9" y="14" textAnchor="middle" fontSize="14" fontWeight="700" fill="#111827">A</text>);
    case "ENDODONCIA_INDICADA":  // triángulo rojo (por realizar)
      return wrap(<path d="M9 3 L15 15 L3 15 Z" fill="none" stroke="#c62828" strokeWidth="1.5" />);
    case "ENDODONCIA":           // triángulo azul (realizada)
      return wrap(<path d="M9 3 L15 15 L3 15 Z" fill="none" stroke="#1565c0" strokeWidth="1.5" />);
    case "CORONA_INDICADA":      // cuadrado rojo con punto (indicada)
      return wrap(<><rect x="3" y="3" width="12" height="12" fill="none" stroke="#c62828" strokeWidth="1.5" /><circle cx="9" cy="9" r="2.2" fill="#c62828" /></>);
    case "CORONA":               // cuadrado azul con punto (realizada)
      return wrap(<><rect x="3" y="3" width="12" height="12" fill="none" stroke="#1565c0" strokeWidth="1.5" /><circle cx="9" cy="9" r="2.2" fill="#1565c0" /></>);
    case "PROTESIS_FIJA_INDICADA":   // caja-línea-caja roja punteada
      return wrap(<g stroke="#c62828" strokeWidth="1.3" fill="none"><rect x="2" y="6" width="4" height="6" /><path d="M6 9 H12" strokeDasharray="1.5 1.5" /><rect x="12" y="6" width="4" height="6" /></g>);
    case "PROTESIS_FIJA":            // caja-línea-caja azul
      return wrap(<g stroke="#1565c0" strokeWidth="1.3" fill="none"><rect x="2" y="6" width="4" height="6" /><path d="M6 9 H12" /><rect x="12" y="6" width="4" height="6" /></g>);
    case "PROTESIS_REMOVIBLE_INDICADA": // paréntesis rojos punteados (----)
      return wrap(<text x="9" y="13" textAnchor="middle" fontSize="11" fill="#c62828">(⋯)</text>);
    case "PROTESIS_REMOVIBLE":       // paréntesis azules
      return wrap(<text x="9" y="13" textAnchor="middle" fontSize="11" fill="#1565c0">(—)</text>);
    case "PROTESIS_TOTAL_INDICADA":  // dos líneas rojas (total indicada)
      return wrap(<g stroke="#c62828" strokeWidth="2"><path d="M3 7 H15" /><path d="M3 11 H15" /></g>);
    case "PROTESIS_TOTAL":           // dos líneas azules (total realizada)
      return wrap(<g stroke="#1565c0" strokeWidth="2"><path d="M3 7 H15" /><path d="M3 11 H15" /></g>);
    case "IMPLANTE":                 // tornillo (cian)
      return wrap(<g stroke="#0891b2" strokeWidth="1.4" fill="none"><path d="M9 3 V15" /><path d="M5 6 H13 M5 9 H13 M5 12 H13" /></g>);
    case "FRACTURA":                 // rayo
      return wrap(<path d="M10 3 L5 9 H9 L7 15 L13 8 H9 Z" fill="#7f1d1d" />);
    case "EN_TRATAMIENTO":           // círculo gris punteado
      return wrap(<circle cx="9" cy="9" r="6" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="2 2" />);
    case "SANO":                     // cuadro blanco con borde
      return wrap(<rect x="3" y="3" width="12" height="12" fill="#fff" stroke="#0a5c61" strokeWidth="1.2" />);
    default:                         // color plano del catálogo
      return wrap(<rect x="3" y="3" width="12" height="12" fill={c} stroke="var(--line)" strokeWidth="1" rx="2" />);
  }
}

export default function OdontogramLegend({ states }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em",
                    color: "var(--petrol)", marginBottom: 10 }}>
        K. Simbología del odontograma
      </div>
      <div style={{ display: "grid", gap: "6px 14px",
                    gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))" }}>
        {states.map((s) => (
          <span key={s.id} style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
            <Symbol code={s.code} color={s.color} />
            <span>{s.label}</span>
          </span>
        ))}
      </div>
      <p style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 10 }}>
        Rojo = patología actual / tratamiento indicado · Azul = tratamiento realizado (según formato MSP 033).
      </p>
    </div>
  );
}
