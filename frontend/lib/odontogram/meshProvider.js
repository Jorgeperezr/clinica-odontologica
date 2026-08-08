"use client";

/**
 * Proveedor de mallas dentales (Sprint 56).
 * ────────────────────────────────────────────────────────────────────
 * El motor de render dejó de saber CÓMO se fabrica un diente. Pide una
 * pieza por su número FDI y recibe siempre lo mismo:
 *
 *   { geometry, scale, metrics }
 *
 *   geometry : BufferGeometry en el marco local canónico
 *   scale    : [x, y, z] a aplicar al objeto
 *   metrics  : { mdWidth, blDepth, crownH, rootH }
 *
 * MARCO LOCAL CANÓNICO (lo asume todo el sistema)
 *
 *   +X  mesio-distal   → a lo largo de la arcada
 *   +Z  vestibular     → hacia fuera de la boca
 *   +Y  oclusal        → corona hacia arriba
 *   origen             → en el cuello (unión amelocementaria)
 *
 * Las `metrics` son las que usan la curva de la arcada para repartir las
 * piezas por su ancho real y la encía para seguir el cuello de cada una.
 * Mientras un proveedor las devuelva correctamente, la colocación, el
 * raycasting, la selección, el historial y la sincronización clínica
 * funcionan igual venga la malla de donde venga.
 *
 * PROVEEDORES
 *
 *   · procedural — el generador de `toothGeometry.js`. Siempre presente,
 *     cero descargas, cero dependencias de licencia.
 *   · gltf       — mallas .glb/.gltf colocadas en `public/models/teeth/`.
 *     Se activa SOLO si encuentra su manifiesto; si falta una pieza,
 *     recurre a la procedural para esa pieza concreta, de modo que un
 *     juego incompleto de modelos nunca deja huecos en la arcada.
 *
 * Para incorporar mallas profesionales en el futuro no hay que tocar
 * este archivo ni la lógica clínica: basta con dejar los ficheros y el
 * manifiesto en la carpeta. Ver `public/models/teeth/README.md`.
 */

import {
  getToothGeometry, toothMetrics, toothScale, toothGeometryKey,
} from "./toothGeometry";

/* ── Proveedor procedural ─────────────────────────────────────────── */

function createProceduralProvider(THREE) {
  const cache = new Map();
  return {
    id: "procedural",
    getTooth(code) {
      return {
        geometry: getToothGeometry(THREE, code, cache),
        scale: toothScale(code),
        metrics: toothMetrics(code),
      };
    },
    /** Cuántas mallas distintas hay realmente en memoria. */
    stats() {
      return { unique: cache.size };
    },
    dispose() {
      cache.forEach((g) => g.dispose());
      cache.clear();
    },
  };
}

/* ── Proveedor de mallas glTF/GLB ─────────────────────────────────── */

/**
 * Normaliza una malla importada al marco local canónico.
 *
 * Los modelos de terceros vienen con la orientación, la escala y el
 * origen que decidiera su autor. En lugar de exigir que se reexporten,
 * el manifiesto puede describir la corrección por pieza o para todo el
 * juego, y aquí se hornea en la geometría una sola vez (no en cada
 * fotograma).
 *
 * @param transform { rotation:[x,y,z] en grados, scale:number|[x,y,z],
 *                    offset:[x,y,z], cervixY:number }
 */
function normalizeGeometry(THREE, geometry, transform = {}) {
  const geo = geometry.clone();
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();

  const rot = transform.rotation || [0, 0, 0];
  e.set(
    (rot[0] * Math.PI) / 180,
    (rot[1] * Math.PI) / 180,
    (rot[2] * Math.PI) / 180,
  );
  q.setFromEuler(e);

  const s = transform.scale ?? 1;
  const sv = Array.isArray(s) ? s : [s, s, s];
  const off = transform.offset || [0, 0, 0];

  m.compose(
    new THREE.Vector3(off[0], off[1], off[2]),
    q,
    new THREE.Vector3(sv[0], sv[1], sv[2]),
  );
  geo.applyMatrix4(m);

  /* El origen debe caer en el cuello. Si el manifiesto no dice dónde
     está, se estima: el cuello es la constricción entre corona y raíz, y
     una aproximación estable es el punto donde la sección horizontal es
     mínima en el tercio central de la pieza. Cuando el autor lo conoce,
     `cervixY` evita la estimación. */
  geo.computeBoundingBox();
  const bb = geo.boundingBox;
  const cervix = transform.cervixY ?? estimateCervix(geo, bb);
  geo.translate(0, -cervix, 0);

  geo.computeBoundingBox();
  geo.computeBoundingSphere();
  if (!geo.attributes.normal) geo.computeVertexNormals();
  return geo;
}

/** Altura de la constricción cervical, por sección horizontal mínima. */
function estimateCervix(geo, bb) {
  const pos = geo.attributes.position;
  const minY = bb.min.y, maxY = bb.max.y;
  const SLICES = 24;
  const span = (maxY - minY) || 1;
  const width = new Float64Array(SLICES);
  const count = new Int32Array(SLICES);

  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i);
    const k = Math.min(SLICES - 1, Math.max(0, Math.floor(((y - minY) / span) * SLICES)));
    width[k] += Math.hypot(pos.getX(i), pos.getZ(i));
    count[k]++;
  }
  let best = -1, bestVal = Infinity;
  // Solo se busca en el tercio central: los extremos siempre son estrechos
  for (let k = Math.floor(SLICES * 0.3); k < Math.floor(SLICES * 0.7); k++) {
    if (!count[k]) continue;
    const avg = width[k] / count[k];
    if (avg < bestVal) { bestVal = avg; best = k; }
  }
  if (best < 0) return (minY + maxY) / 2;
  return minY + ((best + 0.5) / SLICES) * span;
}

/** Medidas de una malla normalizada, para la arcada y la encía. */
function metricsFromGeometry(geo) {
  geo.computeBoundingBox();
  const bb = geo.boundingBox;
  return {
    mdWidth: bb.max.x - bb.min.x,
    blDepth: bb.max.z - bb.min.z,
    crownH: Math.max(0.01, bb.max.y),    // el origen está en el cuello
    rootH: Math.max(0.01, -bb.min.y),
  };
}

/**
 * Carga el juego de mallas descrito por el manifiesto. Devuelve null si
 * no hay manifiesto (caso normal mientras no existan modelos), de modo
 * que el sistema sigue con el proveedor procedural sin ruido en consola.
 */
async function loadGltfSet(THREE, basePath) {
  let manifest;
  try {
    const resp = await fetch(`${basePath}/manifest.json`, { cache: "force-cache" });
    if (!resp.ok) return null;
    manifest = await resp.json();
  } catch {
    return null;   // sin manifiesto: no hay juego de mallas instalado
  }
  if (!manifest || !manifest.teeth || typeof manifest.teeth !== "object") return null;

  let GLTFLoader;
  try {
    ({ GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js"));
  } catch {
    return null;
  }
  const loader = new GLTFLoader();

  /* Compresión opcional. Si el manifiesto declara Draco o Meshopt y el
     decodificador está disponible, se usa; si no, se cargan sin
     comprimir. Nunca es un fallo duro. */
  if (manifest.draco) {
    try {
      const { DRACOLoader } = await import("three/examples/jsm/loaders/DRACOLoader.js");
      const draco = new DRACOLoader();
      draco.setDecoderPath(manifest.draco.decoderPath || `${basePath}/draco/`);
      loader.setDRACOLoader(draco);
    } catch { /* se intenta sin Draco */ }
  }

  const files = new Map();     // fichero → promesa de gltf
  const geometries = new Map(); // código FDI → geometría normalizada

  const loadFile = (file) => {
    if (!files.has(file)) {
      files.set(file, new Promise((resolve) => {
        loader.load(`${basePath}/${file}`, resolve, undefined, () => resolve(null));
      }));
    }
    return files.get(file);
  };

  const entries = Object.entries(manifest.teeth);
  await Promise.all(entries.map(async ([code, spec]) => {
    const file = typeof spec === "string" ? spec : spec.file;
    if (!file) return;
    const gltf = await loadFile(file);
    if (!gltf) return;

    // Dentro del fichero puede haber varias piezas; se elige por nombre
    const nodeName = typeof spec === "object" ? spec.node : null;
    let source = null;
    gltf.scene.traverse((o) => {
      if (source || !o.isMesh) return;
      if (!nodeName || o.name === nodeName) source = o;
    });
    if (!source) return;

    const transform = typeof spec === "object"
      ? { ...(manifest.transform || {}), ...(spec.transform || {}) }
      : (manifest.transform || {});
    geometries.set(String(code), normalizeGeometry(THREE, source.geometry, transform));
  }));

  // Se liberan las escenas originales: ya solo interesa la geometría
  await Promise.all([...files.values()]).then((list) => {
    list.forEach((gltf) => {
      gltf?.scene?.traverse((o) => {
        if (o.isMesh && !geometries.has(o.name)) o.geometry?.dispose?.();
      });
    });
  });

  return geometries.size ? geometries : null;
}

/* ── Selección del proveedor ──────────────────────────────────────── */

/**
 * Devuelve el proveedor de mallas activo. Prioriza el juego glTF si está
 * instalado y recurre al procedural en otro caso, o para las piezas
 * concretas que falten en el juego.
 *
 * @param opts.basePath  carpeta pública del juego de mallas
 * @param opts.prefer    "gltf" | "procedural" (por defecto "gltf")
 */
export async function createMeshProvider(THREE, opts = {}) {
  const { basePath = "/models/teeth", prefer = "gltf" } = opts;
  const procedural = createProceduralProvider(THREE);

  if (prefer === "procedural") return procedural;

  const set = await loadGltfSet(THREE, basePath);
  if (!set) return procedural;

  const metricsCache = new Map();
  return {
    id: "gltf",
    getTooth(code) {
      const key = String(code);
      const geometry = set.get(key);
      // Pieza no incluida en el juego: la cubre la procedural
      if (!geometry) return procedural.getTooth(code);
      if (!metricsCache.has(key)) metricsCache.set(key, metricsFromGeometry(geometry));
      return { geometry, scale: [1, 1, 1], metrics: metricsCache.get(key) };
    },
    stats() {
      return { unique: set.size + procedural.stats().unique, source: "gltf" };
    },
    dispose() {
      set.forEach((g) => g.dispose());
      set.clear();
      procedural.dispose();
    },
  };
}

/** Expuesto para diagnóstico: identifica qué mallas se comparten. */
export { toothGeometryKey };
