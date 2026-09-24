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
 *
 * **Envolvente medida.** Lo anterior era la intención, pero el perfil
 * se calculaba con proporciones fijas de la profundidad de la pieza, y
 * con la inclinación de cada raíz eso no bastaba: la pared vestibular
 * pasaba a unas 0,40 unidades de la arcada y las raíces asomaban por
 * delante —se veían como agujas largas con una franja rosa, que era el
 * margen, cruzando la corona— y también por debajo. Ahora se MIDE la
 * geometría real de cada pieza ya colocada (`medirEnvolvente`) y la
 * pared y el fondo se empujan hasta envolverla. Al medir la malla, sirve
 * igual para las piezas procedurales que para las de un .glb.
 *
 * El mismo constructor, con otro perfil, genera el hueso alveolar.
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
  { n: 0.82, y: 0.00, band: 0 },   // margen libre vestibular
  { n: 1.08, y: -0.22, band: 1 },  // encía libre: fina, pegada al cuello
  { n: 1.06, y: -0.72, band: 1 },  // encía adherida
  { n: 1.02, y: -1.20, band: 2 },  // unión mucogingival
  { n: 0.80, y: -1.62, band: 3 },  // fondo de vestíbulo
  { n: 0.00, y: -1.85, band: 3 },  // base
  { n: -0.76, y: -1.60, band: 3 }, // fondo lingual
  { n: -0.98, y: -1.22, band: 2 },
  { n: -1.04, y: -0.70, band: 1 },
  { n: -1.02, y: -0.24, band: 1 },
  { n: -0.80, y: 0.00, band: 0 },  // margen libre lingual
];

/* La pared vestibular del perfil es deliberadamente ESTRECHA —el ancho
   de la propia pieza—: el volumen real lo da la envolvente medida de
   las raíces más el grosor del tejido. Con una pared ancha y fija
   (1,42–1,46 veces la semiprofundidad, lo de antes) la encía era un tubo
   liso que pasaba por encima de todo; así sigue cada raíz, abulta sobre
   ella —la eminencia del canino es la más visible— y se hunde entre una
   y la siguiente, que es lo que se ve en una encía de verdad. */

/* Tono por banda: multiplica al color del material, nunca lo sustituye.

   Los valores anteriores hacían dos cosas que la mucosa real no hace.
   El margen libre salía MÁS ROJO que la encía adherida cuando en una
   encía sana es al revés —el margen es más pálido y rosado—, y la banda
   de mucosa alveolar quedaba en rgb(125,51,54), casi granate, frente a
   rgb(169,100,102) de la referencia. El conjunto se leía como carne
   cruda y no como tejido sano.

   Las proporciones de abajo salen de convertir a sRGB los L*a*b* de
   mucosa oral sana y tomarlas RESPECTO A LA ENCÍA ADHERIDA, que se deja
   donde estaba: así se corrige la relación entre bandas —que es lo que
   estaba mal— sin alterar el nivel general, que ya estaba ajustado
   contra la escena iluminada.

   La diferencia entre encía adherida y mucosa alveolar no es un detalle
   estético: la unión mucogingival es una referencia clínica, y si las
   dos bandas se parecen demasiado deja de verse dónde está. */
const BAND_SHADE = [
  [1.03, 0.98, 0.97],   // margen libre: más pálido y rosado que la adherida
  [1.00, 0.92, 0.91],   // encía adherida: queda como estaba (referencia)
  [0.90, 0.70, 0.73],   // unión mucogingival: transición
  [0.80, 0.54, 0.58],   // mucosa alveolar: más roja y oscura
];
/* Se subió el contraste entre la adherida y la mucosa: con los valores
   anteriores, en el tema claro toda la encía se leía como un único rosa
   y desaparecía la unión mucogingival, que es una referencia clínica. */

/* Perfil del hueso alveolar. La cresta queda por debajo del cuello (en
   una boca sana, 1,5–2 mm apical a la unión amelocementaria) y el
   volumen es algo más estrecho que la encía, que lo recubre. */
export const PERFIL_HUESO = [
  { n: 0.00, y: 0.02, band: 0 },   // cresta, dentro de la raíz
  { n: 0.78, y: 0.00, band: 0 },   // cresta vestibular
  { n: 0.94, y: -0.30, band: 1 },  // tabla vestibular (la envolvente la ajusta a cada raíz)
  { n: 0.95, y: -0.90, band: 1 },
  { n: 0.88, y: -1.45, band: 2 },  // hueso basal
  { n: 0.56, y: -1.72, band: 2 },
  { n: 0.00, y: -1.80, band: 2 },
  { n: -0.56, y: -1.70, band: 2 },
  { n: -0.86, y: -1.36, band: 2 },
  { n: -0.92, y: -0.80, band: 1 },
  { n: -0.90, y: -0.28, band: 1 },
  { n: -0.78, y: 0.00, band: 0 },  // cresta lingual/palatina
];

/* Hueso: la cresta y las tablas corticales, algo más claras; el hueso
   basal, más apagado. */
export const TONO_HUESO = [
  [1.04, 1.03, 1.00],
  [1.00, 1.00, 1.00],
  [0.93, 0.91, 0.88],
];

const SUB = 2;          // subdivisiones por tramo del perfil
// Muestras a lo largo del arco por pieza. Eran 7: con la pared siguiendo
// cada raíz, tan pocas dejaban las eminencias facetadas.
const PER_TOOTH = 12;

/** Catmull-Rom cerrada: suaviza el perfil sin tener que escribir más puntos. */
function sampleProfile(p = PROFILE) {
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
        /* El margen vestibular subía solo un 32 % de la papila y la papila
           no llegaba a formarse: quedaba un festón bajo y redondo. La
           banda rosa que se atribuía a subirlo más era en realidad la
           encía dibujada del revés (ver el sentido de los triángulos). */
        lift: Math.max(0, 1 - Math.abs(f(p0.y, p1.y, p2.y, p3.y)) / 0.5)
            * (0.66 + 0.34 * Math.max(0, 1 - Math.abs(f(p0.n, p1.n, p2.n, p3.n)) / 0.7)),
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
 * @param placements  piezas: { length, halfDepth, eminence, marginY }
 * @param opts        { upper, perfil, tonos, envolvente, holgura, papila }
 *   perfil      perfil transversal (por omisión, el de la encía)
 *   tonos       tono por banda del perfil
 *   envolvente  la de `medirEnvolvente`: si se da, la pared y el fondo
 *               se empujan hasta dejar dentro las raíces
 *   holgura     distancia mínima entre raíz y superficie
 *   papila      multiplicador de la altura de la papila (el tabique
 *               óseo es más bajo que la papila gingival)
 */
export function buildGingivaGeometry(THREE, curve, placements, opts = {}) {
  const {
    upper = false, perfil = PROFILE, tonos = BAND_SHADE,
    envolvente = null, holgura = 0.08, papila = 1,
  } = opts;
  const dir = upper ? -1 : 1;              // hacia dónde "crece" la encía
  const prof = sampleProfile(perfil);
  const ring = prof.length;
  // Profundidad nominal del perfil: la del punto más apical.
  const fondoPerfil = Math.max(...perfil.map((q) => -q.y));

  const centers = placements.map((p) => p.length);
  const first = centers[0], last = centers[centers.length - 1];
  // La encía se extiende algo más allá de la última pieza (zona retromolar).
  // Con 1,0 la punta afinada dejaba asomar la cara distal del tercer molar.
  const from = Math.max(0, first - 1.2);
  const to = Math.min(curve.total, last + 1.2);

  /**
   * Interpola una magnitud de las piezas vecinas a lo largo del arco.
   * Se usa para la semiprofundidad y —lo importante— para la ALTURA DEL
   * MARGEN: cada pieza tiene su cuello a distinta altura (curva de Spee,
   * coronas de distinto tamaño), así que un margen a altura constante se
   * despegaba del cuello en unas piezas y montaba sobre la corona en
   * otras. Interpolándolo, el margen recorre la arcada pegado al cuello.
   */
  function lerpAt(l, field) {
    let i = 0;
    while (i < centers.length - 1 && centers[i + 1] < l) i++;
    const a = placements[i], b = placements[Math.min(i + 1, placements.length - 1)];
    const span = (b.length - a.length) || 1;
    const t = Math.max(0, Math.min(1, (l - a.length) / span));
    const smooth = t * t * (3 - 2 * t);
    return a[field] + (b[field] - a[field]) * smooth;
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

  /**
   * Relieve de la tabla vestibular: eminencia sobre cada raíz y DEPRESIÓN
   * entre raíces contiguas. Sin las depresiones el conjunto de
   * eminencias se funde en una superficie continua y la encía vuelve a
   * leerse como un bloque; el hueso alveolar real se hunde entre raíz y
   * raíz, y eso es lo que dibuja el relieve característico.
   */
  function eminenceAt(l) {
    let e = 0;
    placements.forEach((p) => {
      const d = (l - p.length) / 0.40;
      e += (p.eminence || 0) * Math.exp(-d * d);
    });
    for (let i = 0; i < centers.length - 1; i++) {
      const mid = (centers[i] + centers[i + 1]) / 2;
      const d = (l - mid) / 0.26;
      e -= 0.055 * Math.exp(-d * d);
    }
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
    const hd = lerpAt(l, "halfDepth");
    const my = lerpAt(l, "marginY");
    /* La papila y el grosor del tejido cambian a lo largo de la arcada:
       entre incisivos es alta y estrecha, entre molares baja y ancha, y
       la encía posterior es sensiblemente más gruesa. Con un valor único
       para toda la arcada el tejido se lee como una pieza extruida. */
    const pap = lerpAt(l, "papillaH");
    const thick = lerpAt(l, "thickness");
    const scal = scallopAt(l);
    const emin = eminenceAt(l);
    const taper = endTaper(l);

    /* Fondo: si alguna raíz de este tramo llega más abajo que el perfil,
       se estira la parte apical —no el margen— hasta cubrirla. */
    let estira = 1;
    if (envolvente) {
      const apice = envolvente.apice(l);
      if (apice !== null) {
        const hace = Math.abs(apice - my) + holgura * 1.6;
        const nominal = fondoPerfil * (0.85 + 0.15 * thick);
        if (hace > nominal) estira = (hace - 0.34) / (nominal - 0.34);
      }
    }

    for (let r = 0; r <= ring; r++) {
      const p = prof[r % ring];
      // La eminencia solo abulta la vertiente vestibular (n > 0)
      let nOff = (p.n * hd * thick + (p.n > 0.5 ? emin * Math.min(1, p.n) : 0)) * taper;
      let py = p.y * taper * (0.85 + 0.15 * thick);
      if (py < -0.34) py = -0.34 + (py + 0.34) * estira;
      const y = my + dir * (py + pap * papila * scal * p.lift);

      /* Pared: por debajo del margen, nunca más cerca de la arcada que
         la raíz más saliente a esa altura. El margen y la cresta quedan
         como estaban, porque tienen que cortar la corona. Se entra de
         forma gradual en los primeros 0,2 para no dejar un escalón. */
      if (envolvente && p.y < -0.02) {
        const peso = Math.min(1, -p.y / 0.2);
        const lim = envolvente.en(l, y);
        if (lim) {
          if (p.n > 0) {
            const hasta = lim.vest + holgura;
            if (hasta > nOff) nOff += (hasta - nOff) * peso;
          } else if (p.n < 0) {
            const hasta = lim.ling - holgura;
            if (hasta < nOff) nOff += (hasta - nOff) * peso;
          }
        }
      }

      pos.push(fr.x + fr.nx * nOff, y, fr.z + fr.nz * nOff);
      /* Misma escala a lo largo del arco que a lo ancho del perfil (unas
         4,6 unidades de perímetro): antes el punteado salía estirado
         casi 3 a 1 y se leía como vetas verticales. */
      uvs.push(l / 4.6, r / ring);

      const sh = tonos[Math.min(p.band, tonos.length - 1)];
      /* Sombra del surco. El punto donde la encía se encuentra con el
         diente es una hendidura estrecha a la que casi no llega luz; sin
         ella el tejido parece pegado con adhesivo al diente y el conjunto
         se lee como una prótesis de resina. Se refuerza en la tronera,
         que es la zona más cerrada. */
      const sulcus = 1 - 0.30 * p.margin * Math.max(0, 1 - Math.abs(p.n) / 1.25);
      const ao = sulcus * (1 - 0.18 * p.margin * scal);
      col.push(sh[0] * ao, sh[1] * ao, sh[2] * ao);
    }
  }

  /* Sentido de los triángulos: antihorario visto DESDE FUERA, que es lo
     que three toma como cara delantera.

     Hasta ahora estaba al revés en las dos arcadas, y era el defecto de
     fondo de todo el modelo: con `FrontSide` la GPU descartaba la pared
     de la encía que mira a la cámara y dibujaba la cara interior de la
     pared de enfrente. Por eso las raíces se veían por delante de la
     encía (la pared que las tapaba no se pintaba), lo que asomaba sobre
     las coronas como una franja rosa era el margen del otro lado visto
     por dentro, y desde abajo la base aparecía abierta. Se comprobó
     dibujando la encía por su cara trasera: con eso envolvía los
     dientes. Dar la vuelta al orden es el arreglo correcto, porque
     además deja las normales hacia fuera y la luz se calcula bien. */
  const stride = ring + 1;
  for (let s = 0; s < samples; s++) {
    for (let r = 0; r < ring; r++) {
      const a = s * stride + r, b = (s + 1) * stride + r;
      if (upper) {
        idx.push(a, b + 1, a + 1);
        idx.push(a, b, b + 1);
      } else {
        idx.push(a, a + 1, b + 1);
        idx.push(a, b + 1, b);
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
    const sh = tonos[tonos.length - 1];
    col.push(sh[0] * 0.9, sh[1] * 0.9, sh[2] * 0.9);
    for (let r = 0; r < ring; r++) {
      if (flip) idx.push(base + r, base + r + 1, c);
      else idx.push(base + r + 1, base + r, c);
    }
  }
  cap(0, upper);
  cap(samples, !upper);

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

/**
 * Mide hasta dónde llegan las piezas de una arcada, en coordenadas de la
 * propia arcada: a lo largo (l), hacia fuera (n) y en altura (y).
 *
 * Devuelve dos consultas:
 *   en(l, y)  → { vest, ling }: lo más vestibular y lo más lingual que
 *               llega alguna pieza en ese tramo y a esa altura, o null
 *   apice(l)  → la altura del ápice más profundo en ese tramo, o null
 *
 * Cada vértice se lleva al marco de SU pieza (punto, tangente y normal de
 * la arcada en su posición). Dentro del ancho de un diente la curvatura
 * de la arcada es despreciable, así que eso basta y evita buscar el punto
 * más cercano de la curva para cada vértice.
 *
 * @param piezas  [{ mesh, spot }] con la malla ya posicionada
 * @param upper   arcada superior (las raíces crecen hacia +y)
 */
export function medirEnvolvente(THREE, piezas, { upper = false, paso = 0.08 } = {}) {
  const celdas = new Map();        // "iL,iY" → { vest, ling }
  const apices = new Map();        // iL → y más apical
  const v = new THREE.Vector3();

  for (const { mesh, spot } of piezas) {
    mesh.updateMatrix();
    const pos = mesh.geometry.attributes.position;
    // Con unos pocos miles de muestras por pieza sobra: las celdas son
    // de 0,08 unidades, más gruesas que la separación entre vértices.
    const salto = Math.max(1, Math.floor(pos.count / 3000));
    for (let i = 0; i < pos.count; i += salto) {
      v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrix);
      const rx = v.x - spot.x, rz = v.z - spot.z;
      const n = rx * spot.nx + rz * spot.nz;
      const l = spot.length + rx * spot.tx + rz * spot.tz;
      const iL = Math.round(l / paso), iY = Math.round(v.y / paso);
      const k = `${iL},${iY}`;
      const c = celdas.get(k);
      if (!c) celdas.set(k, { vest: n, ling: n });
      else { if (n > c.vest) c.vest = n; if (n < c.ling) c.ling = n; }
      const a = apices.get(iL);
      if (a === undefined || (upper ? v.y > a : v.y < a)) apices.set(iL, v.y);
    }
  }

  return {
    en(l, y) {
      // Vecindad de una celda en cada sentido: sin ella, una celda vacía
      // entre dos llenas deja un hoyo en la pared.
      /* Vecindad con caída: una celda vecina cuenta, pero algo menos
         cuanto más lejos. Tomar el máximo plano de las vecinas (lo de
         antes) tapaba el hueco entre dos raíces y la pared salía lisa;
         con la caída se hunde entre raíz y raíz, como el hueso real. */
      const iL = Math.round(l / paso), iY = Math.round(y / paso);
      let vest = -Infinity, ling = Infinity;
      for (let a = -2; a <= 2; a++) {
        const caida = 0.018 * a * a;
        for (let b = -1; b <= 1; b++) {
          const c = celdas.get(`${iL + a},${iY + b}`);
          if (c) {
            if (c.vest - caida > vest) vest = c.vest - caida;
            if (c.ling + caida < ling) ling = c.ling + caida;
          }
        }
      }
      return vest === -Infinity ? null : { vest, ling };
    },
    apice(l) {
      const iL = Math.round(l / paso);
      let y = null;
      for (let a = -2; a <= 2; a++) {
        const ap = apices.get(iL + a);
        if (ap !== undefined && (y === null || (upper ? ap > y : ap < y))) y = ap;
      }
      return y;
    },
  };
}
