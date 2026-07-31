"use client";

/**
 * Encía (Sprint 53).
 * ────────────────────────────────────────────────────────────────────
 * Sustituye los dos toros achatados que hacían de encía. Un toro es una
 * circunferencia y las arcadas son elipses, así que la encía anterior
 * atravesaba las piezas de una zona y dejaba las raíces al aire en otra;
 * además, al ser un tubo liso y semitransparente, se leía como un aro de
 * plástico gris y no como tejido.
 *
 * Aquí la encía se genera sobre LA MISMA curva que coloca los dientes
 * (`archCurve.js`), recorriéndola con un perfil cerrado que reproduce la
 * anatomía gingival real:
 *
 *   · margen libre festoneado — cénit sobre cada pieza y papila
 *     interdental levantada en cada tronera;
 *   · eminencias radiculares — el relieve que dejan las raíces sobre la
 *     tabla vestibular, marcado en los caninos;
 *   · encía adherida, unión mucogingival y fondo de vestíbulo;
 *   · vertiente lingual/palatina cerrando el volumen.
 *
 * La cresta del perfil pasa por dentro del diente a propósito: así el
 * borde visible de la encía es la INTERSECCIÓN con la pieza, que sigue
 * su contorno de forma natural y no puede dejar huecos. El margen se
 * sitúa por encima de la unión amelocementaria, como en una encía sana.
 *
 * El volumen es cerrado (incluidas las tapas de los extremos), de modo
 * que las raíces quedan dentro y no se ven flotando.
 */

/* Perfil transversal de la encía, recorrido en sentido cerrado.
   `n` se expresa en múltiplos de la semiprofundidad local de la pieza
   (así el perfil se adapta solo a un incisivo o a un molar) e `y` en
   unidades de escena respecto del margen. `band` selecciona el tono.

   El collar del margen va deliberadamente POR DENTRO del contorno de la
   pieza (n < 1) y la pared se abre enseguida por fuera: la encía emerge
   entonces desde debajo del cuello y su borde visible es la intersección
   con el diente. Con el collar justo en el contorno (n ≈ 1) bastaba el
   error de muestreo para que asomara por delante, y se veía una línea
   recta cruzando todas las coronas. */
const PROFILE = [
  { n: 0.00, y: 0.06, band: 0 },   // cresta (queda dentro de la pieza)
  { n: 0.80, y: 0.00, band: 0 },   // margen libre vestibular
  { n: 1.42, y: -0.34, band: 1 },  // encía libre (pared que cae deprisa)
  { n: 1.46, y: -0.78, band: 1 },  // encía adherida sobre la eminencia
  { n: 1.30, y: -1.26, band: 2 },  // unión mucogingival
  { n: 0.80, y: -1.62, band: 3 },  // fondo de vestíbulo
  { n: 0.00, y: -1.85, band: 3 },  // base
  { n: -0.76, y: -1.60, band: 3 }, // fondo lingual
  { n: -1.16, y: -1.22, band: 2 },
  { n: -1.34, y: -0.70, band: 1 },
  { n: -1.26, y: -0.26, band: 1 },
  { n: -0.78, y: 0.00, band: 0 },  // margen libre lingual
];

/** Tono por banda: multiplica al color del material, nunca lo sustituye. */
const BAND_SHADE = [
  [1.02, 0.90, 0.90],   // margen: rosa coral
  [1.00, 0.95, 0.94],   // encía adherida: pálida y mate
  [0.97, 0.81, 0.82],   // unión mucogingival
  [0.88, 0.63, 0.66],   // mucosa alveolar: más roja y oscura
];

const SUB = 2;          // subdivisiones por tramo del perfil
const PER_TOOTH = 7;    // muestras a lo largo del arco por pieza

/** Catmull-Rom cerrada: suaviza el perfil sin tener que escribir más puntos. */
function sampleProfile() {
  const p = PROFILE;
  const n = p.length;
  const out = [];
  for (let i = 0; i < n; i++) {
    const p0 = p[(i - 1 + n) % n], p1 = p[i], p2 = p[(i + 1) % n], p3 = p[(i + 2) % n];
    for (let s = 0; s < SUB; s++) {
      const t = s / SUB, t2 = t * t, t3 = t2 * t;
      const f = (a, b, c, d) =>
        0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
      out.push({
        n: f(p0.n, p1.n, p2.n, p3.n),
        y: f(p0.y, p1.y, p2.y, p3.y),
        band: p1.band,
        // Cuánto pertenece este punto al margen (para el festón y la sombra)
        margin: Math.max(0, 1 - Math.abs(f(p0.y, p1.y, p2.y, p3.y)) / 0.45),
        /* Cuánto acompaña este punto al festón. La papila es una PUNTA
           entre dos dientes, no un pliegue de todo el tejido: si se sube
           la sección entera, el margen vestibular monta sobre la cara
           del diente y se ve una banda rosa cruzando las coronas. */
        lift: Math.max(0, 1 - Math.abs(f(p0.y, p1.y, p2.y, p3.y)) / 0.5)
            * (0.32 + 0.68 * Math.max(0, 1 - Math.abs(f(p0.n, p1.n, p2.n, p3.n)) / 0.7)),
      });
    }
  }
  return out;
}

/**
 * Construye la malla de una encía completa.
 *
 * @param THREE
 * @param curve       curva de la arcada (archCurve)
 * @param placements  piezas colocadas: { length, halfDepth, eminence }
 * @param opts        { upper, marginY, papilla }
 */
export function buildGingivaGeometry(THREE, curve, placements, opts = {}) {
  const { upper = false, marginY = 0, papilla = 0.22 } = opts;
  const dir = upper ? -1 : 1;              // hacia dónde "crece" la encía
  const prof = sampleProfile();
  const ring = prof.length;

  const centers = placements.map((p) => p.length);
  const first = centers[0], last = centers[centers.length - 1];
  // La encía se extiende algo más allá de la última pieza (zona retromolar)
  const from = Math.max(0, first - 1.0);
  const to = Math.min(curve.total, last + 1.0);

  /** Semiprofundidad local: interpolada entre las piezas vecinas. */
  function halfDepthAt(l) {
    let i = 0;
    while (i < centers.length - 1 && centers[i + 1] < l) i++;
    const a = placements[i], b = placements[Math.min(i + 1, placements.length - 1)];
    const span = (b.length - a.length) || 1;
    const t = Math.max(0, Math.min(1, (l - a.length) / span));
    return a.halfDepth + (b.halfDepth - a.halfDepth) * t;
  }

  /**
   * Festón del margen: 0 sobre el centro de cada pieza (cénit gingival)
   * y 1 en la tronera entre dos piezas (punta de la papila).
   */
  function scallopAt(l) {
    let i = 0, best = Infinity;
    centers.forEach((c, k) => {
      const d = Math.abs(l - c);
      if (d < best) { best = d; i = k; }
    });
    const side = l >= centers[i] ? 1 : -1;
    const neighbour = centers[i + side];
    if (neighbour === undefined) {
      // Extremo de la arcada: el margen desciende suavemente
      return -Math.min(1, best / 0.5) * 0.55;
    }
    const half = Math.abs(neighbour - centers[i]) / 2 || 1;
    const t = Math.min(1, best / half);
    // Exponente alto: la papila sube solo cerca de la tronera, en punta,
    // en vez de levantar una meseta entre pieza y pieza.
    return Math.pow(t, 2.2);
  }

  /** Eminencia radicular: relieve que deja la raíz en la tabla vestibular. */
  function eminenceAt(l) {
    let e = 0;
    placements.forEach((p) => {
      const d = (l - p.length) / 0.42;
      e += (p.eminence || 0) * Math.exp(-d * d);
    });
    return e;
  }

  const samples = Math.max(24, Math.round((placements.length * PER_TOOTH)));
  const pos = [], uvs = [], col = [], idx = [];

  /**
   * Afinado de los extremos: sin él, el volumen se corta en seco tras la
   * última muela y su tapa se ve como una placa plana. Aquí la encía se
   * cierra en punta redondeada, como la tuberosidad y el trígono
   * retromolar.
   */
  function endTaper(l) {
    // El afinado ocupa el tramo que sobra tras la última pieza, de modo
    // que la encía llega entera hasta el fondo de la arcada y ninguna
    // raíz queda a la vista.
    const d = Math.min(l - from, to - l) / 0.62;
    const t = Math.min(1, Math.max(0, d));
    return 0.12 + 0.88 * (t * t * (3 - 2 * t));
  }

  for (let s = 0; s <= samples; s++) {
    const l = from + ((to - from) * s) / samples;
    const fr = curve.frameAtLength(l);
    const hd = halfDepthAt(l);
    const scal = scallopAt(l);
    const emin = eminenceAt(l);
    const taper = endTaper(l);

    for (let r = 0; r <= ring; r++) {
      const p = prof[r % ring];
      // La eminencia solo abulta la vertiente vestibular (n > 0)
      const nOff = (p.n * hd + (p.n > 0.5 ? emin * Math.min(1, p.n) : 0)) * taper;
      pos.push(
        fr.x + fr.nx * nOff,
        marginY + dir * (p.y * taper + papilla * scal * p.lift),
        fr.z + fr.nz * nOff,
      );
      uvs.push((l / curve.total) * 6, r / ring);

      const sh = BAND_SHADE[p.band];
      // Sombra de contacto en la tronera: oscurece la papila junto al diente
      const ao = 1 - 0.16 * p.margin * scal;
      col.push(sh[0] * ao, sh[1] * ao, sh[2] * ao);
    }
  }

  const stride = ring + 1;
  for (let s = 0; s < samples; s++) {
    for (let r = 0; r < ring; r++) {
      const a = s * stride + r, b = (s + 1) * stride + r;
      if (upper) {
        idx.push(a, a + 1, b + 1);
        idx.push(a, b + 1, b);
      } else {
        idx.push(a, b + 1, a + 1);
        idx.push(a, b, b + 1);
      }
    }
  }

  /** Tapas de los extremos: el volumen debe quedar cerrado. */
  function cap(sampleIndex, flip) {
    const base = sampleIndex * stride;
    let cx = 0, cy = 0, cz = 0;
    for (let r = 0; r < ring; r++) {
      cx += pos[(base + r) * 3]; cy += pos[(base + r) * 3 + 1]; cz += pos[(base + r) * 3 + 2];
    }
    const c = pos.length / 3;
    pos.push(cx / ring, cy / ring, cz / ring);
    uvs.push(0.5, 0.5);
    const sh = BAND_SHADE[3];
    col.push(sh[0] * 0.9, sh[1] * 0.9, sh[2] * 0.9);
    for (let r = 0; r < ring; r++) {
      if (flip) idx.push(base + r, base + r + 1, c);
      else idx.push(base + r + 1, base + r, c);
    }
  }
  cap(0, !upper);
  cap(samples, upper);

  const geo = new THREE.BufferGeometry();
  geo.setIndex(idx);
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  geo.computeVertexNormals();

  // Costura del perfil: promediar las normales de los vértices repetidos
  const nAttr = geo.attributes.normal;
  for (let s = 0; s <= samples; s++) {
    const a = s * stride, b = s * stride + ring;
    const nx = nAttr.getX(a) + nAttr.getX(b);
    const ny = nAttr.getY(a) + nAttr.getY(b);
    const nz = nAttr.getZ(a) + nAttr.getZ(b);
    const len = Math.hypot(nx, ny, nz) || 1;
    nAttr.setXYZ(a, nx / len, ny / len, nz / len);
    nAttr.setXYZ(b, nx / len, ny / len, nz / len);
  }
  nAttr.needsUpdate = true;
  geo.computeBoundingSphere();
  return geo;
}
