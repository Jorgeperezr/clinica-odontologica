"use client";

/**
 * Configuración → Apariencia de documentos (Sprint 63).
 * ────────────────────────────────────────────────────────────────────
 * Pantalla única desde la que se define el aspecto de TODOS los
 * documentos de la clínica: hoja, márgenes, tipografía, paleta,
 * encabezado, pie, logotipo, tablas, firmas y marca de agua. Lo que se
 * guarda aquí lo consume `apps.common.document_style` en el servidor,
 * que es el único punto por el que los generadores obtienen colores y
 * medidas: ningún documento lleva ya estilos escritos a mano.
 *
 * EXCEPCIÓN: el formulario MSP HCU-033/2021 no usa este motor, por ser
 * un formato oficial con diseño legalmente fijado. Se avisa en pantalla
 * para que nadie espere que cambie al tocar estos ajustes.
 *
 * La vista previa no pide nada al servidor: reproduce en HTML las mismas
 * reglas de dibujo que `document_style` aplica en el PDF (posición del
 * encabezado, línea separadora, pie, firma, marca de agua), de modo que
 * el cambio se ve al instante mientras se mueve un control. Por eso solo
 * se muestran ajustes que el motor aplica de verdad; si un ajuste no se
 * dibujara, la vista previa mentiría.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { api } from "./api";
import { logoSrc } from "./theme";

/* ── Ajustes disponibles ──────────────────────────────────────────────
   Cada entrada describe un control. Añadir un ajuste nuevo al motor es
   añadir una línea aquí: el formulario y la vista previa lo recogen
   solos. */
const GROUPS = [
  {
    key: "page",
    label: "Página",
    hint: "Tamaño de hoja, orientación y márgenes de todos los documentos.",
    fields: [
      { k: "size", t: "select", label: "Tamaño de hoja",
        options: [["A4", "A4 (210 × 297 mm)"], ["LETTER", "Carta (216 × 279 mm)"], ["LEGAL", "Oficio (216 × 356 mm)"]] },
      { k: "orientation", t: "select", label: "Orientación",
        options: [["portrait", "Vertical"], ["landscape", "Horizontal"]] },
      { k: "margin_top_mm", t: "num", label: "Margen superior", suffix: "mm", min: 5, max: 60 },
      { k: "margin_bottom_mm", t: "num", label: "Margen inferior", suffix: "mm", min: 5, max: 60 },
      { k: "margin_left_mm", t: "num", label: "Margen izquierdo", suffix: "mm", min: 5, max: 60 },
      { k: "margin_right_mm", t: "num", label: "Margen derecho", suffix: "mm", min: 5, max: 60 },
      { k: "block_spacing_mm", t: "num", label: "Aire bajo el encabezado", suffix: "mm", min: 0, max: 20 },
    ],
  },
  {
    key: "typography",
    label: "Tipografía",
    hint: "Familias incorporadas en el generador de PDF: no requieren instalar fuentes.",
    fields: [
      { k: "family", t: "select", label: "Familia",
        options: [["Helvetica", "Helvetica (sans)"], ["Times", "Times (serif)"], ["Courier", "Courier (monoespaciada)"]] },
      { k: "size_pt", t: "num", label: "Tamaño del texto", suffix: "pt", min: 6, max: 16, step: 0.5 },
      { k: "line_height", t: "num", label: "Interlineado", suffix: "×", min: 1, max: 2.2, step: 0.05 },
      { k: "title_size_pt", t: "num", label: "Tamaño del título", suffix: "pt", min: 10, max: 30, step: 0.5 },
      { k: "subtitle_size_pt", t: "num", label: "Tamaño del subtítulo", suffix: "pt", min: 8, max: 24, step: 0.5 },
      { k: "color", t: "color", label: "Color del texto" },
    ],
  },
  {
    key: "palette",
    label: "Colores",
    hint: "El color principal vacío hereda el color de marca de la clínica.",
    fields: [
      { k: "primary", t: "color", label: "Color principal", inherit: "marca de la clínica" },
      { k: "secondary", t: "color", label: "Color secundario" },
      { k: "title", t: "color", label: "Color de títulos" },
      { k: "subtitle", t: "color", label: "Color de subtítulos" },
      { k: "separator", t: "color", label: "Líneas separadoras" },
      { k: "alert", t: "color", label: "Avisos y urgencias" },
      { k: "table_header_bg", t: "color", label: "Fondo de cabecera de tabla" },
      { k: "table_header_text", t: "color", label: "Texto de cabecera de tabla" },
    ],
  },
  {
    key: "header",
    label: "Encabezado",
    hint: "Franja superior con el logotipo y los datos de la clínica.",
    fields: [
      { k: "enabled", t: "bool", label: "Mostrar encabezado" },
      { k: "align", t: "select", label: "Alineación del texto",
        options: [["left", "Izquierda"], ["center", "Centro"], ["right", "Derecha"]] },
      { k: "height_mm", t: "num", label: "Alto de la franja", suffix: "mm", min: 10, max: 60 },
      { k: "show_logo", t: "bool", label: "Logotipo" },
      { k: "show_clinic_name", t: "bool", label: "Nombre de la clínica" },
      { k: "show_professional", t: "bool", label: "Profesional" },
      { k: "show_specialty", t: "bool", label: "Especialidad del profesional" },
      { k: "show_address", t: "bool", label: "Dirección" },
      { k: "show_phone", t: "bool", label: "Teléfono" },
      { k: "show_email", t: "bool", label: "Correo electrónico" },
      { k: "background", t: "color", label: "Fondo de la franja", inherit: "sin fondo" },
      { k: "text_color", t: "color", label: "Color del texto", inherit: "color principal" },
    ],
  },
  {
    key: "logo",
    label: "Logotipo",
    hint: "Se toma el logotipo cargado en Personalización.",
    fields: [
      { k: "position", t: "select", label: "Posición",
        options: [["header_left", "Izquierda"], ["header_center", "Centro"], ["header_right", "Derecha"]] },
      { k: "width_mm", t: "num", label: "Ancho", suffix: "mm", min: 8, max: 70 },
      { k: "height_mm", t: "num", label: "Alto", suffix: "mm", min: 6, max: 50 },
      { k: "gap_mm", t: "num", label: "Separación del texto", suffix: "mm", min: 0, max: 20 },
      { k: "opacity", t: "num", label: "Opacidad", min: 0.1, max: 1, step: 0.05 },
    ],
  },
  {
    key: "footer",
    label: "Pie de página",
    hint: "Se repite en todas las páginas del documento.",
    fields: [
      { k: "enabled", t: "bool", label: "Mostrar pie" },
      { k: "align", t: "select", label: "Alineación",
        options: [["left", "Izquierda"], ["center", "Centro"], ["right", "Derecha"]] },
      { k: "show_clinic", t: "bool", label: "Datos de la clínica" },
      { k: "show_date", t: "bool", label: "Fecha de emisión" },
      { k: "show_time", t: "bool", label: "Incluir la hora" },
      { k: "show_page_numbers", t: "bool", label: "Número de página" },
      { k: "text", t: "text", label: "Texto adicional", placeholder: "Ej: Documento de uso interno" },
      { k: "legal_text", t: "text", label: "Aviso legal", placeholder: "Ej: Datos protegidos por la LOPDP" },
      { k: "text_color", t: "color", label: "Color del texto", inherit: "color secundario" },
    ],
  },
  {
    key: "tables",
    label: "Tablas",
    hint: "Aplica a presupuestos, planes de tratamiento y reportes.",
    fields: [
      { k: "shaded", t: "bool", label: "Cabecera con fondo" },
      { k: "zebra", t: "bool", label: "Filas alternas" },
      { k: "zebra_color", t: "color", label: "Color de la fila alterna" },
      { k: "header_bg", t: "color", label: "Fondo de la cabecera", inherit: "color de la paleta" },
      { k: "border_color", t: "color", label: "Color del borde", inherit: "líneas separadoras" },
      { k: "border_width", t: "num", label: "Grosor del borde", suffix: "pt", min: 0, max: 2, step: 0.1 },
      { k: "cell_padding_mm", t: "num", label: "Relleno de celda", suffix: "mm", min: 0.5, max: 6, step: 0.5 },
      { k: "row_spacing_mm", t: "num", label: "Aire entre filas", suffix: "mm", min: 0, max: 5, step: 0.5 },
    ],
  },
  {
    key: "signature",
    label: "Firmas",
    hint: "Bloque de firma de solicitudes de examen y consentimientos.",
    fields: [
      { k: "show_image", t: "bool", label: "Firma digitalizada" },
      { k: "show_name", t: "bool", label: "Nombre del firmante" },
      { k: "show_specialty", t: "bool", label: "Especialidad" },
      { k: "show_license", t: "bool", label: "Registro profesional" },
      { k: "position", t: "select", label: "Posición (firma única)",
        options: [["left", "Izquierda"], ["center", "Centro"], ["right", "Derecha"]] },
      { k: "width_mm", t: "num", label: "Ancho de la firma", suffix: "mm", min: 20, max: 80 },
      { k: "height_mm", t: "num", label: "Alto de la firma", suffix: "mm", min: 8, max: 40 },
    ],
  },
  {
    key: "watermark",
    label: "Marca de agua",
    hint: "Útil para marcar borradores o copias.",
    fields: [
      { k: "enabled", t: "bool", label: "Activar marca de agua" },
      { k: "text", t: "text", label: "Texto", placeholder: "Ej: BORRADOR" },
      { k: "size_pt", t: "num", label: "Tamaño", suffix: "pt", min: 20, max: 140 },
      { k: "opacity", t: "num", label: "Opacidad", min: 0.02, max: 0.5, step: 0.01 },
      { k: "rotation", t: "num", label: "Inclinación", suffix: "°", min: -90, max: 90, step: 5 },
    ],
  },
];

/* Medidas de hoja en milímetros, iguales a las de reportlab. */
const PAGE_MM = { A4: [210, 297], LETTER: [215.9, 279.4], LEGAL: [215.9, 355.6] };
const PT_MM = 25.4 / 72;          // 1 punto tipográfico en milímetros
const FALLBACK_PRIMARY = "#0e5c63";

const num = (v, d) => (Number.isFinite(Number(v)) ? Number(v) : d);

export default function DocumentAppearance() {
  const [settings, setSettings] = useState(null);
  const [saved, setSaved] = useState(null);
  const [brand, setBrand] = useState({});
  const [open, setOpen] = useState("page");
  const [zoom, setZoom] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const [aResp, bResp] = await Promise.all([
        api("/config/document-appearance/"), api("/config/branding/"),
      ]);
      const a = await aResp.json();
      if (!aResp.ok) throw new Error(a?.error?.message || `Error ${aResp.status}`);
      setSettings(a);
      setSaved(JSON.stringify(a));
      if (bResp.ok) setBrand(await bResp.json());
    } catch (err) { setError(err.message || "No se pudo cargar la apariencia."); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const dirty = settings && saved !== JSON.stringify(settings);

  function set(group, key, value) {
    setOkMsg("");
    setSettings((prev) => ({ ...prev, [group]: { ...prev[group], [key]: value } }));
  }

  async function save() {
    setBusy(true); setError(""); setOkMsg("");
    try {
      const resp = await api("/config/document-appearance/", {
        method: "PATCH", body: JSON.stringify(settings),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.error?.message || `Error ${resp.status}`);
      setSettings(data);
      setSaved(JSON.stringify(data));
      setOkMsg("Apariencia guardada. Los documentos que se generen a partir de ahora la usarán.");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function restore() {
    if (!window.confirm("¿Restablecer la apariencia por defecto de todos los documentos?")) return;
    setBusy(true); setError(""); setOkMsg("");
    try {
      const resp = await api("/config/document-appearance/", { method: "DELETE" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.error?.message || `Error ${resp.status}`);
      setSettings(data);
      setSaved(JSON.stringify(data));
      setOkMsg("Apariencia restablecida.");
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (error && !settings) return <div className="error-box">{error}</div>;
  if (!settings) return <div className="empty">Cargando apariencia…</div>;

  return (
    <div>
      {error && <div className="error-box">{error}</div>}
      {okMsg && <div className="success-box">✓ {okMsg}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
                    gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
        <p style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0, maxWidth: 620 }}>
          Define el aspecto de todos los documentos que emite la clínica. Los cambios se ven
          en la vista previa al instante y se aplican a los documentos que se generen después
          de guardar. El formulario MSP HCU-033/2021 conserva su diseño oficial y no se ve
          afectado.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" disabled={busy} onClick={restore}>Restablecer</button>
          <button className="btn btn-primary" disabled={busy || !dirty} onClick={save}>
            {dirty ? "Guardar cambios" : "Sin cambios"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 420px) 1fr", gap: 20,
                    alignItems: "start" }}>
        {/* Controles */}
        <div style={{ display: "grid", gap: 8 }}>
          {GROUPS.map((g) => (
            <div key={g.key} className="card" style={{ padding: 0, overflow: "hidden" }}>
              <button
                onClick={() => setOpen(open === g.key ? "" : g.key)}
                style={{ width: "100%", display: "flex", justifyContent: "space-between",
                         alignItems: "center", padding: "12px 14px", border: "none",
                         background: open === g.key ? "var(--petrol-soft)" : "transparent",
                         cursor: "pointer", fontWeight: 700, fontSize: 14, color: "var(--ink)" }}>
                {g.label}
                <span style={{ color: "var(--ink-soft)", fontSize: 12 }}>
                  {open === g.key ? "▲" : "▼"}
                </span>
              </button>
              {open === g.key && (
                <div style={{ padding: "12px 14px 16px" }}>
                  <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 0, marginBottom: 12 }}>
                    {g.hint}
                  </p>
                  <div style={{ display: "grid", gap: 10 }}>
                    {g.fields.map((f) => (
                      <Field key={f.k} field={f} value={settings[g.key]?.[f.k]}
                             onChange={(v) => set(g.key, f.k, v)} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Vista previa */}
        <div style={{ position: "sticky", top: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                        marginBottom: 8 }}>
            <strong style={{ fontSize: 13 }}>Vista previa</strong>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {[0.8, 1, 1.25].map((z) => (
                <button key={z} onClick={() => setZoom(z)}
                        className={z === zoom ? "btn btn-primary" : "btn btn-ghost"}
                        style={{ padding: "3px 10px", fontSize: 12 }}>
                  {Math.round(z * 100)}%
                </button>
              ))}
            </div>
          </div>
          <div style={{ overflow: "auto", padding: 12, borderRadius: "var(--radius)",
                        background: "var(--bg-alt, #eef1f4)", border: "1px solid var(--line)" }}>
            <DocumentPreviewPage settings={settings} brand={brand} zoom={zoom} />
          </div>
          <p style={{ fontSize: 12, color: "var(--ink-soft)", marginTop: 8 }}>
            Representación del documento con los ajustes actuales. El contenido es de
            ejemplo; lo que se reproduce es la maqueta que comparten todos los documentos.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ── Controles ───────────────────────────────────────────────────────── */
function Field({ field, value, onChange }) {
  const label = (
    <label style={{ fontSize: 12, color: "var(--ink-soft)", fontWeight: 600 }}>
      {field.label}
    </label>
  );

  if (field.t === "bool") {
    return (
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        {field.label}
      </label>
    );
  }

  if (field.t === "select") {
    return (
      <div>
        {label}
        <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}
                style={{ width: "100%", padding: "7px 9px", border: "1px solid var(--line)",
                         borderRadius: 8, marginTop: 3 }}>
          {field.options.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>
    );
  }

  if (field.t === "text") {
    return (
      <div>
        {label}
        <input value={value ?? ""} placeholder={field.placeholder || ""}
               onChange={(e) => onChange(e.target.value)}
               style={{ width: "100%", padding: "7px 9px", border: "1px solid var(--line)",
                        borderRadius: 8, marginTop: 3 }} />
      </div>
    );
  }

  if (field.t === "color") {
    const empty = !value;
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input type="color" value={empty ? "#888888" : value}
               onChange={(e) => onChange(e.target.value)}
               style={{ width: 42, height: 30, padding: 2, border: "1px solid var(--line)",
                        borderRadius: 8, opacity: empty ? 0.45 : 1 }} />
        <div style={{ flex: 1 }}>
          {label}
          {field.inherit && (
            <div style={{ fontSize: 11, color: "var(--ink-soft)" }}>
              {empty ? `Automático: ${field.inherit}` : (
                <button className="btn btn-ghost" style={{ padding: 0, fontSize: 11 }}
                        onClick={() => onChange("")}>
                  Usar {field.inherit}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Numérico con deslizador: se ve el efecto mientras se arrastra.
  const step = field.step || 1;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        {label}
        <span className="tabular" style={{ fontSize: 12 }}>
          {num(value, field.min)}{field.suffix ? ` ${field.suffix}` : ""}
        </span>
      </div>
      <input type="range" min={field.min} max={field.max} step={step}
             value={num(value, field.min)}
             onChange={(e) => onChange(Number(e.target.value))}
             style={{ width: "100%", marginTop: 2 }} />
    </div>
  );
}

/* ── Vista previa ─────────────────────────────────────────────────────
   Reproduce la maqueta del PDF: encabezado a `margin_top`, línea
   separadora a `margin_top + alto`, contenido tras `block_spacing`,
   firma anclada sobre el pie y pie a `margin_bottom`. Las medidas van en
   milímetros y se convierten a píxeles con un único factor, igual que
   reportlab convierte a puntos. */
function DocumentPreviewPage({ settings, brand, zoom }) {
  const { page, typography: ty, palette: pal, header: hd, footer: ft,
          logo: lg, tables: tb, signature: sg, watermark: wm } = settings;

  const [pw, ph] = PAGE_MM[String(page.size || "A4").toUpperCase()] || PAGE_MM.A4;
  const [W, H] = page.orientation === "landscape" ? [ph, pw] : [pw, ph];
  const K = 2.35 * zoom;                       // píxeles por milímetro
  const mmPx = (v) => v * K;
  const ptPx = (v) => v * PT_MM * K;

  const mt = num(page.margin_top_mm, 20);
  const mb = num(page.margin_bottom_mm, 18);
  const ml = num(page.margin_left_mm, 20);
  const mr = num(page.margin_right_mm, 20);
  const contentW = W - ml - mr;

  const primary = pal.primary || brand?.theme?.primary || FALLBACK_PRIMARY;
  const ink = ty.color || "#1f2937";
  const secondary = pal.secondary || "#6b7280";
  const separator = pal.separator || "#d1d5db";
  const fontFamily = ({ Times: "Georgia, 'Times New Roman', serif",
                        Courier: "'Courier New', monospace" })[ty.family]
                     || "Helvetica, Arial, sans-serif";
  const size = num(ty.size_pt, 10);

  const clinic = {
    name: brand?.display_name || "Clínica Dental",
    address: brand?.address || "Av. Principal 123 y Secundaria",
    phone: brand?.phone || "0999999999",
    email: brand?.email || "info@clinica.ec",
  };

  const hEnabled = hd.enabled !== false;
  const hHeight = num(hd.height_mm, 26);
  const logoW = num(lg.width_mm, 26);
  const logoH = num(lg.height_mm, 20);
  const showLogo = hEnabled && hd.show_logo !== false && !!brand?.logo_url;
  const logoLeft = lg.position === "header_center" ? (W - logoW) / 2
                 : lg.position === "header_right" ? W - mr - logoW
                 : ml;
  const textLeft = showLogo && lg.position === "header_left"
    ? ml + logoW + num(lg.gap_mm, 4) : ml;

  const align = hd.align === "center" ? "center" : hd.align === "right" ? "right" : "left";
  const headerLines = [];
  if (hd.show_clinic_name !== false) {
    headerLines.push({ text: clinic.name, pt: num(ty.subtitle_size_pt, 12) + 2,
                       bold: true, color: hd.text_color || primary });
  }
  if (hd.show_professional !== false) {
    const bits = ["Dra. Ana Pérez"];
    if (hd.show_specialty !== false) bits.push("Odontología general");
    headerLines.push({ text: bits.join(" · "), pt: size, bold: false, color: secondary });
  }
  const contact = [];
  if (hd.show_address !== false) contact.push(clinic.address);
  if (hd.show_phone !== false) contact.push(`Tel. ${clinic.phone}`);
  if (hd.show_email !== false) contact.push(clinic.email);
  if (contact.length) {
    headerLines.push({ text: contact.join(" · "), pt: size - 1.5, bold: false, color: secondary });
  }

  const contentTop = hEnabled
    ? mt + hHeight + num(page.block_spacing_mm, 5)
    : mt;

  /* Pie: línea a mb + 6 mm y texto sobre la línea de base de mb. */
  const footerBits = [];
  if (ft.show_clinic !== false) footerBits.push(clinic.name, clinic.address, clinic.phone);
  if (ft.text) footerBits.push(ft.text);
  if (ft.show_date !== false) footerBits.push(ft.show_time ? "08/08/2026 10:24" : "08/08/2026");
  if (ft.show_page_numbers !== false) footerBits.push("Página 1");

  const tableRows = [
    ["Restauración de resina", "1.6", "$45.00"],
    ["Profilaxis", "—", "$30.00"],
    ["Radiografía periapical", "2.4", "$12.00"],
  ];
  const headerBg = tb.header_bg || pal.table_header_bg || primary;
  const cellPad = num(tb.cell_padding_mm, 2);
  const vPad = cellPad * 0.6 + num(tb.row_spacing_mm, 0);
  /* La rejilla se dibuja como separación entre celdas sobre un fondo del
     color del borde: es la forma de conseguir una línea única, igual que
     el GRID de reportlab, sin que se dupliquen los bordes contiguos. */
  const gridLine = num(tb.border_width, 0.6) > 0
    ? Math.max(0.5, num(tb.border_width, 0.6)) : 0;
  const gridColor = tb.border_color || separator;

  /* Bloque de firma: anclado sobre el pie, con la misma reserva de
     52 mm que usa el generador. */
  const sigW = Math.max(num(sg.width_mm, 45) + 15, 55);
  const sigLeft = sg.position === "left" ? ml
                : sg.position === "center" ? ml + (contentW - sigW) / 2
                : W - mr - sigW;
  const contentH = Math.max(0, H - contentTop - (mb + 52) - 3);

  /* El ejemplo se recorta al hueco que queda libre entre el encabezado y
     el bloque de firma. En vez de cortar por la mitad un bloque —que se
     leería como un fallo de maqueta y no como lo que es— se van
     retirando bloques del final hasta que lo que queda entra: con
     márgenes amplios o en horizontal, sencillamente se muestra menos
     documento de muestra. */
  const contentRef = useRef(null);
  const [detail, setDetail] = useState(3);
  const shape = `${W}|${H}|${contentTop}|${contentH}|${size}|${cellPad}|${vPad}|${ty.family}`;
  useLayoutEffect(() => { setDetail(3); }, [shape]);
  useLayoutEffect(() => {
    const el = contentRef.current;
    if (el && detail > 0 && el.scrollHeight > el.clientHeight + 1) {
      setDetail((d) => d - 1);
    }
  }, [detail, shape]);

  return (
    <div style={{ position: "relative", width: mmPx(W), height: mmPx(H), background: "#fff",
                  boxShadow: "0 2px 14px rgba(0,0,0,.18)", overflow: "hidden",
                  fontFamily, color: ink, margin: "0 auto" }}>

      {/* Marca de agua: en el PDF gira en sentido antihorario. Se centra
          con translate y no con flex, porque un texto más ancho que la
          hoja se recortaría solo por la izquierda. */}
      {wm.enabled && wm.text && (
        <div style={{ position: "absolute", left: "50%", top: "50%",
                      transform: `translate(-50%, -50%) rotate(${-num(wm.rotation, 45)}deg)`,
                      fontSize: ptPx(num(wm.size_pt, 60)), fontWeight: 700,
                      color: secondary, opacity: num(wm.opacity, 0.08),
                      whiteSpace: "nowrap", pointerEvents: "none" }}>
          {wm.text}
        </div>
      )}

      {/* Encabezado */}
      {hEnabled && (
        <>
          {hd.background && (
            <div style={{ position: "absolute", left: 0, top: mmPx(mt), width: "100%",
                          height: mmPx(hHeight), background: hd.background }} />
          )}
          {showLogo && (
            <img src={logoSrc(brand.logo_url, brand.updated_at)} alt=""
                 style={{ position: "absolute", left: mmPx(logoLeft), top: mmPx(mt),
                          width: mmPx(logoW), height: mmPx(logoH), objectFit: "contain",
                          opacity: num(lg.opacity, 1) }} />
          )}
          <div style={{ position: "absolute", top: mmPx(mt + 2.4),
                        left: mmPx(align === "left" ? textLeft : ml),
                        width: mmPx(align === "left" ? W - textLeft - mr : contentW),
                        textAlign: align }}>
            {headerLines.map((l, i) => (
              <div key={i} style={{ fontSize: ptPx(l.pt), fontWeight: l.bold ? 700 : 400,
                                    color: l.color, lineHeight: 1.35, whiteSpace: "nowrap",
                                    overflow: "hidden", textOverflow: "ellipsis" }}>
                {l.text}
              </div>
            ))}
          </div>
          <div style={{ position: "absolute", left: mmPx(ml), top: mmPx(mt + hHeight),
                        width: mmPx(contentW), borderTop: `1px solid ${separator}` }} />
        </>
      )}

      {/* Contenido de ejemplo */}
      <div ref={contentRef}
           style={{ position: "absolute", left: mmPx(ml), top: mmPx(contentTop),
                    width: mmPx(contentW), maxHeight: mmPx(contentH), overflow: "hidden" }}>
        <div style={{ textAlign: "center", fontWeight: 700,
                      fontSize: ptPx(num(ty.title_size_pt, 16) - 2),
                      color: pal.title || "#111827" }}>
          SOLICITUD DE EXAMEN COMPLEMENTARIO
        </div>

        {detail >= 2 && (
          <>
            <div style={{ marginTop: mmPx(6), fontWeight: 700, fontSize: ptPx(size),
                          color: primary, letterSpacing: 0.4 }}>
              DATOS DEL PACIENTE
            </div>
            <div style={{ borderTop: `1px solid ${separator}`, marginTop: mmPx(0.8) }} />
            <div style={{ display: "flex", gap: mmPx(10), marginTop: mmPx(2.5) }}>
              {[["Nombre completo", "María Fernanda Torres"], ["Identificación", "1712345678"],
                ["Edad", "34 años"]].map(([k, v]) => (
                <div key={k}>
                  <div style={{ fontSize: ptPx(size - 1.5), color: secondary }}>{k.toUpperCase()}</div>
                  <div style={{ fontSize: ptPx(size + 0.5), lineHeight: num(ty.line_height, 1.35) }}>{v}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* La tabla no se retira nunca: es lo que se está ajustando al
            abrir el grupo «Tablas». En el último escalón se queda con una
            sola fila. */}
        <div style={{ marginTop: mmPx(6), fontWeight: 700, fontSize: ptPx(size),
                      color: primary, letterSpacing: 0.4 }}>
          DETALLE
        </div>
        <div style={{ borderTop: `1px solid ${separator}`, marginTop: mmPx(0.8) }} />

        {/* No se usa <table> a propósito: las reglas globales del panel
            (mayúsculas en th, resaltado al pasar el ratón, bordes) se
            colarían en la vista previa y esta dejaría de reflejar el PDF. */}
        <div style={{ marginTop: mmPx(3), fontSize: ptPx(size - 1),
                      display: "grid", gridTemplateColumns: `1fr ${mmPx(18)}px ${mmPx(24)}px`,
                      gap: gridLine, background: gridColor,
                      border: gridLine ? `${gridLine}px solid ${gridColor}` : "none" }}>
          {[["Tratamiento", "Pieza", "Valor"],
            ...(detail >= 1 ? tableRows : tableRows.slice(0, 1))].map((row, i) =>
            row.map((cell, j) => (
              <div key={`${i}-${j}`} style={{
                background: i === 0
                  ? (tb.shaded !== false ? headerBg : "#ffffff")
                  : (tb.zebra !== false && i % 2 === 0 ? (tb.zebra_color || "#f9fafb") : "#ffffff"),
                color: i === 0 && tb.shaded !== false
                  ? (pal.table_header_text || "#ffffff") : ink,
                fontWeight: i === 0 ? 700 : 400,
                padding: `${mmPx(vPad)}px ${mmPx(cellPad)}px`,
              }}>{cell}</div>
            )),
          )}
        </div>

        {detail >= 3 && (
          <div style={{ marginTop: mmPx(5), fontSize: ptPx(size),
                        lineHeight: num(ty.line_height, 1.35), color: ink }}>
            Se solicita la valoración radiográfica indicada para completar el diagnóstico
            del paciente antes de iniciar el plan de tratamiento acordado en consulta.
          </div>
        )}
      </div>

      {/* Firma, anclada sobre el pie igual que en el documento */}
      <div style={{ position: "absolute", left: mmPx(sigLeft), width: mmPx(sigW),
                    bottom: mmPx(mb + 26), textAlign: "center" }}>
        {sg.show_image !== false && (
          <div style={{ height: mmPx(num(sg.height_mm, 18)), display: "flex",
                        alignItems: "flex-end", justifyContent: "center" }}>
            <svg width={mmPx(num(sg.width_mm, 45))} height={mmPx(num(sg.height_mm, 18)) * 0.8}
                 viewBox="0 0 100 32" aria-hidden="true">
              <path d="M4 24 C 18 2, 26 30, 38 16 S 58 2, 68 20 S 84 26, 96 8"
                    fill="none" stroke={ink} strokeWidth="2.2" strokeLinecap="round" />
            </svg>
          </div>
        )}
        <div style={{ borderTop: `1px solid ${ink}` }} />
        <div style={{ fontWeight: 700, fontSize: ptPx(size - 0.5), marginTop: mmPx(1.4) }}>
          Firma y sello
        </div>
        {sg.show_name !== false && (
          <div style={{ fontSize: ptPx(size - 1.5), color: secondary }}>Dra. Ana Pérez</div>
        )}
        {(sg.show_specialty !== false || sg.show_license !== false) && (
          <div style={{ fontSize: ptPx(size - 1.5), color: secondary }}>
            {[sg.show_specialty !== false ? "Odontología general" : null,
              sg.show_license !== false ? "Reg. 1002-2019" : null]
              .filter(Boolean).join(" · ")}
          </div>
        )}
      </div>

      {/* Pie */}
      {ft.enabled !== false && (
        <>
          <div style={{ position: "absolute", left: mmPx(ml), bottom: mmPx(mb + 6),
                        width: mmPx(contentW), borderTop: `1px solid ${separator}` }} />
          <div style={{ position: "absolute", left: mmPx(ml), bottom: mmPx(mb - 1),
                        width: mmPx(contentW), fontSize: ptPx(size - 2),
                        color: ft.text_color || secondary,
                        textAlign: ft.align === "left" ? "left"
                                 : ft.align === "right" ? "right" : "center" }}>
            {footerBits.join("  ·  ")}
          </div>
          {ft.legal_text && (
            <div style={{ position: "absolute", left: mmPx(ml), bottom: mmPx(mb - 5),
                          width: mmPx(contentW), fontSize: ptPx(size - 3),
                          color: ft.text_color || secondary, textAlign: "center" }}>
              {ft.legal_text}
            </div>
          )}
        </>
      )}
    </div>
  );
}
