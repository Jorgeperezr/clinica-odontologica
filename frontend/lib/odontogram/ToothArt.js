"use client";

/**
 * Set de ilustraciones dentales (Sprint 47).
 * ────────────────────────────────────────────────────────────────────
 * Ilustraciones vectoriales dibujadas a medida, no imágenes de mapa de
 * bits. Tres razones clínicas y técnicas:
 *
 *  1. Escalan sin pérdida: en la pantalla retina de una tablet, donde
 *     el odontólogo trabaja a un palmo de distancia, un PNG se ve
 *     borroso y un SVG no.
 *  2. Heredan el tema: el esmalte, la dentina y los contornos usan los
 *     tokens del sistema, así que funcionan en claro y en oscuro sin
 *     mantener dos juegos de imágenes.
 *  3. Cada superficie sigue siendo una región clicable con su color
 *     clínico encima, que es lo que un dibujo plano no permitiría.
 *
 * La morfología sigue la anatomía real: la familia se deduce del último
 * dígito FDI y el número de raíces del cuadrante. Un molar superior
 * lleva tres raíces, uno inferior dos, y el primer premolar superior
 * dos; el resto, una. La corona cambia de perfil y de número de
 * cúspides según la familia.
 *
 * Sistema de coordenadas: 40 de ancho × 96 de alto, corona arriba.
 * La arcada inferior se dibuja reflejada por el componente que lo usa.
 */

const VB_W = 40;
const VB_H = 96;
const CROWN_H = 46;

/** Familia dental a partir del último dígito FDI. */
export function toothFamily(code) {
  const s = String(code);
  const n = Number(s.slice(-1));
  const deciduous = ["5", "6", "7", "8"].includes(s[0]);
  if (deciduous) {
    if (n <= 2) return "incisivo";
    if (n === 3) return "canino";
    return "molar";           // 4 y 5 temporales son molares
  }
  if (n <= 2) return "incisivo";
  if (n === 3) return "canino";
  if (n <= 5) return "premolar";
  return "molar";
}

/** ¿Pieza del maxilar superior? (cuadrantes 1, 2, 5 y 6) */
export function isUpper(code) {
  return ["1", "2", "5", "6"].includes(String(code)[0]);
}

/** ¿Pieza temporal? (cuadrantes 5 a 8) */
export function isDeciduous(code) {
  return ["5", "6", "7", "8"].includes(String(code)[0]);
}

/** Número de raíces según anatomía real. */
function rootCount(code) {
  const fam = toothFamily(code);
  const up = isUpper(code);
  const n = Number(String(code).slice(-1));
  if (fam === "molar") return up ? 3 : 2;
  if (fam === "premolar") return up && n === 4 ? 2 : 1;
  return 1;
}

/* ── Perfil de la corona por familia ──────────────────────────────
   Cada perfil devuelve el contorno de la corona en el espacio
   (0,0)-(40,46): borde incisal u oclusal arriba, cuello abajo. */
function crownOutline(fam, slim) {
  const w = VB_W, h = CROWN_H;
  const m = slim ? 7 : 3.5;              // margen lateral (piezas temporales más estrechas)
  const nk = slim ? 9 : 6;               // estrechamiento del cuello
  switch (fam) {
    case "incisivo":
      // Borde incisal recto, caras proximales que convergen al cuello
      return `M${m + 1} ${h} C${m - 0.5} ${h * 0.55} ${m} ${h * 0.28} ${m + 2} ${h * 0.16}
              Q${w / 2} ${h * 0.03} ${w - m - 2} ${h * 0.16}
              C${w - m} ${h * 0.28} ${w - m + 0.5} ${h * 0.55} ${w - m - 1} ${h} Z`;
    case "canino":
      // Cúspide única y prominente en el centro
      return `M${m + 1} ${h} C${m - 1} ${h * 0.55} ${m + 1} ${h * 0.3} ${m + 3} ${h * 0.22}
              L${w / 2} ${h * 0.02} L${w - m - 3} ${h * 0.22}
              C${w - m - 1} ${h * 0.3} ${w - m + 1} ${h * 0.55} ${w - m - 1} ${h} Z`;
    case "premolar":
      // Dos cúspides (vestibular y palatina) con surco central
      return `M${m + 1} ${h} C${m - 1} ${h * 0.6} ${m} ${h * 0.3} ${m + 2} ${h * 0.2}
              Q${w * 0.3} ${h * 0.04} ${w * 0.42} ${h * 0.17}
              Q${w / 2} ${h * 0.24} ${w * 0.58} ${h * 0.17}
              Q${w * 0.7} ${h * 0.04} ${w - m - 2} ${h * 0.2}
              C${w - m} ${h * 0.3} ${w - m + 1} ${h * 0.6} ${w - m - 1} ${h} Z`;
    default:
      // Molar: cuatro cúspides y corona más ancha
      return `M${m - 0.5} ${h} C${m - 2} ${h * 0.62} ${m - 1} ${h * 0.3} ${m + 1} ${h * 0.19}
              Q${w * 0.2} ${h * 0.05} ${w * 0.31} ${h * 0.16}
              Q${w * 0.4} ${h * 0.23} ${w / 2} ${h * 0.14}
              Q${w * 0.6} ${h * 0.23} ${w * 0.69} ${h * 0.16}
              Q${w * 0.8} ${h * 0.05} ${w - m - 1} ${h * 0.19}
              C${w - m + 1} ${h * 0.3} ${w - m + 2} ${h * 0.62} ${w - m + 0.5} ${h} Z`;
  }
}

/** Raíces: divergen desde el cuello hacia el ápice. */
function rootPaths(code, slim) {
  const n = rootCount(code);
  const top = CROWN_H - 2;
  const len = isDeciduous(code) ? 30 : 44;   // las temporales tienen raíz más corta
  const apex = top + len;
  const cx = VB_W / 2;

  if (n === 1) {
    const halfW = slim ? 6 : 7.5;
    return [`M${cx - halfW} ${top} C${cx - halfW + 1} ${top + len * 0.55}
             ${cx - 2.5} ${apex - 6} ${cx} ${apex}
             C${cx + 2.5} ${apex - 6} ${cx + halfW - 1} ${top + len * 0.55} ${cx + halfW} ${top} Z`];
  }
  if (n === 2) {
    const spread = slim ? 7 : 9;
    return [-1, 1].map((s) => {
      const b = cx + s * spread;          // ápice desplazado
      const o = cx + s * 3.5;             // arranque en el cuello
      return `M${o - 4.5} ${top} C${o - 4} ${top + len * 0.5} ${b - 3} ${apex - 6} ${b} ${apex}
              C${b + 3} ${apex - 6} ${o + 4} ${top + len * 0.5} ${o + 4.5} ${top} Z`;
    });
  }
  // Tres raíces (molar superior): dos vestibulares y una palatina más larga
  const trio = [
    { o: cx - 8, b: cx - 12, l: len * 0.86 },
    { o: cx + 8, b: cx + 12, l: len * 0.86 },
    { o: cx, b: cx + 1, l: len },
  ];
  return trio.map(({ o, b, l }) => {
    const ap = top + l;
    return `M${o - 4} ${top} C${o - 3.5} ${top + l * 0.5} ${b - 2.5} ${ap - 5} ${b} ${ap}
            C${b + 2.5} ${ap - 5} ${o + 3.5} ${top + l * 0.5} ${o + 4} ${top} Z`;
  });
}

/** Surcos y cúspides: el detalle que da lectura anatómica. */
function occlusalDetail(fam) {
  const h = CROWN_H, w = VB_W;
  switch (fam) {
    case "incisivo":
      return [`M${w * 0.3} ${h * 0.14} L${w * 0.3} ${h * 0.3}`,
              `M${w * 0.5} ${h * 0.11} L${w * 0.5} ${h * 0.32}`,
              `M${w * 0.7} ${h * 0.14} L${w * 0.7} ${h * 0.3}`];
    case "canino":
      return [`M${w * 0.5} ${h * 0.06} L${w * 0.5} ${h * 0.42}`,
              `M${w * 0.32} ${h * 0.26} L${w * 0.42} ${h * 0.34}`,
              `M${w * 0.68} ${h * 0.26} L${w * 0.58} ${h * 0.34}`];
    case "premolar":
      return [`M${w * 0.42} ${h * 0.17} Q${w / 2} ${h * 0.3} ${w * 0.58} ${h * 0.17}`,
              `M${w * 0.5} ${h * 0.26} L${w * 0.5} ${h * 0.44}`];
    default:
      return [`M${w * 0.31} ${h * 0.16} Q${w / 2} ${h * 0.3} ${w * 0.69} ${h * 0.16}`,
              `M${w * 0.5} ${h * 0.14} L${w * 0.5} ${h * 0.46}`,
              `M${w * 0.34} ${h * 0.34} L${w * 0.66} ${h * 0.34}`];
  }
}

/**
 * Ilustración de una pieza dental.
 *
 * @param code      número FDI
 * @param fill      color clínico dominante (o null para esmalte natural)
 * @param selected  resalta el contorno
 * @param size      alto en píxeles (el ancho se deriva)
 */
export default function ToothArt({ code, fill, selected, size = 58, onClick, title }) {
  const fam = toothFamily(code);
  const slim = isDeciduous(code);
  const upper = isUpper(code);
  const gid = `enamel-${code}`;
  const w = (size * VB_W) / VB_H;

  const crown = crownOutline(fam, slim);
  const roots = rootPaths(code, slim);
  const detail = occlusalDetail(fam);

  return (
    <svg width={w} height={size} viewBox={`0 0 ${VB_W} ${VB_H}`}
         onClick={onClick} role="img"
         aria-label={title || `Pieza ${code}`}
         style={{
           cursor: onClick ? "pointer" : "default",
           // La arcada inferior es la imagen especular de la superior
           transform: upper ? "none" : "scaleY(-1)",
           overflow: "visible",
           transition: "filter var(--dur-fast) var(--ease)",
           filter: selected ? "drop-shadow(0 0 3px var(--petrol))" : "none",
         }}>
      <defs>
        {/* Degradado de esmalte: más claro en la cúspide, con cuerpo hacia el cuello */}
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--tooth-enamel-hi)" />
          <stop offset="55%" stopColor="var(--tooth-enamel)" />
          <stop offset="100%" stopColor="var(--tooth-dentin)" />
        </linearGradient>
      </defs>

      {/* Raíces, por debajo de la corona */}
      {roots.map((d, i) => (
        <path key={i} d={d} fill="var(--tooth-root)"
              stroke="var(--tooth-stroke)" strokeWidth="0.9"
              strokeLinejoin="round" />
      ))}

      {/* Corona: esmalte natural o color clínico si la pieza tiene estado */}
      <path d={crown} fill={fill || `url(#${gid})`}
            stroke={selected ? "var(--petrol)" : "var(--tooth-stroke)"}
            strokeWidth={selected ? 1.8 : 1}
            strokeLinejoin="round" />

      {/* Surcos y cúspides */}
      {detail.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="var(--tooth-groove)"
              strokeWidth="0.85" strokeLinecap="round" opacity={fill ? 0.45 : 0.7} />
      ))}
    </svg>
  );
}
