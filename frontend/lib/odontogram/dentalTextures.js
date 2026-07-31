"use client";

/**
 * Texturas dentales procedurales (Sprint 53).
 * ────────────────────────────────────────────────────────────────────
 * Se dibujan en un canvas al abrir la pestaña y se comparten entre todas
 * las piezas. Ninguna se descarga: cero bytes de red, cero dependencias
 * de terceros y cero problemas de licencia, igual que con la geometría.
 *
 * Por qué hacen falta. Un material con rugosidad constante devuelve un
 * brillo perfectamente uniforme, y ese es el rasgo que delata el
 * plástico: en un diente real el brillo se rompe porque la superficie
 * tiene microrrelieve (perikimatíes en el esmalte, punteado de cáscara
 * de naranja en la encía adherida). Variar la rugosidad por textura es
 * lo que más acerca el render al aspecto clínico, y cuesta una sola
 * lectura de textura por píxel.
 *
 * Las coordenadas UV de `toothGeometry` recorren v = 0 en el ápice y
 * v = 1 en oclusal, con el cuello en v ≈ 0.35, de modo que las texturas
 * pueden cambiar de comportamiento entre raíz y corona.
 */

const SIZE = 256;

/** Ruido de valor determinista: mismo resultado en cada carga. */
function makeNoise(seed) {
  const perm = new Uint8Array(512);
  let s = seed >>> 0;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const base = new Uint8Array(256);
  for (let i = 0; i < 256; i++) base[i] = i;
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [base[i], base[j]] = [base[j], base[i]];
  }
  for (let i = 0; i < 512; i++) perm[i] = base[i & 255];

  const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
  const grad = (h, x, y) => ((h & 1) ? -x : x) + ((h & 2) ? -y : y);

  return function noise2(x, y) {
    const xi = Math.floor(x) & 255, yi = Math.floor(y) & 255;
    const xf = x - Math.floor(x), yf = y - Math.floor(y);
    const u = fade(xf), v = fade(yf);
    const aa = perm[perm[xi] + yi], ab = perm[perm[xi] + yi + 1];
    const ba = perm[perm[xi + 1] + yi], bb = perm[perm[xi + 1] + yi + 1];
    const lerp = (a, b, t) => a + (b - a) * t;
    return lerp(
      lerp(grad(aa, xf, yf), grad(ba, xf - 1, yf), u),
      lerp(grad(ab, xf, yf - 1), grad(bb, xf - 1, yf - 1), u),
      v,
    );
  };
}

/** Ruido fractal en [0,1]. */
function fbm(noise, x, y, octaves = 4) {
  let v = 0, amp = 0.5, freq = 1, norm = 0;
  for (let o = 0; o < octaves; o++) {
    v += noise(x * freq, y * freq) * amp;
    norm += amp;
    amp *= 0.5; freq *= 2;
  }
  return v / norm * 0.5 + 0.5;
}

function canvasTexture(THREE, draw, { srgb = false, repeat = [1, 1] } = {}) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = SIZE;
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(SIZE, SIZE);
  draw(img.data);
  ctx.putImageData(img, 0, 0);

  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeat[0], repeat[1]);
  tex.anisotropy = 4;
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/**
 * Rugosidad del diente. La corona es lisa con vetas suaves; la raíz,
 * claramente más mate porque el cemento no está pulido. La franja del
 * cuello hace de transición.
 */
export function enamelRoughnessTexture(THREE) {
  const noise = makeNoise(20482);
  return canvasTexture(THREE, (d) => {
    for (let y = 0; y < SIZE; y++) {
      // v = 0 abajo del canvas (ápice), v = 1 arriba (oclusal)
      const v = 1 - y / (SIZE - 1);
      const isCrown = Math.min(1, Math.max(0, (v - 0.30) / 0.12));
      for (let x = 0; x < SIZE; x++) {
        const n = fbm(noise, (x / SIZE) * 7, (y / SIZE) * 7);
        // Corona pulida (≈0.22) frente a raíz mate (≈0.62)
        const rough = (0.66 - 0.36 * isCrown) + (n - 0.5) * 0.20;
        const c = Math.round(Math.min(1, Math.max(0, rough)) * 255);
        const i = (y * SIZE + x) * 4;
        d[i] = d[i + 1] = d[i + 2] = c;
        d[i + 3] = 255;
      }
    }
  });
}

/**
 * Rugosidad gingival: el margen libre está húmedo y brilla; la encía
 * adherida es mate. Esa diferencia de acabado es la que hace que el
 * tejido parezca mucosa y no goma.
 */
export function gingivaRoughnessTexture(THREE) {
  const noise = makeNoise(9091);
  return canvasTexture(THREE, (d) => {
    for (let y = 0; y < SIZE; y++) {
      const v = y / (SIZE - 1);
      const wet = Math.max(
        Math.exp(-((v - 0.02) ** 2) / 0.004),
        Math.exp(-((v - 0.98) ** 2) / 0.004),
      );
      const mucosa = Math.exp(-((v - 0.5) ** 2) / 0.05);
      for (let x = 0; x < SIZE; x++) {
        const n = fbm(noise, (x / SIZE) * 9, (y / SIZE) * 9, 3);
        const rough = 0.72 - 0.34 * wet - 0.14 * mucosa + (n - 0.5) * 0.12;
        const c = Math.round(Math.min(1, Math.max(0, rough)) * 255);
        const i = (y * SIZE + x) * 4;
        d[i] = d[i + 1] = d[i + 2] = c;
        d[i + 3] = 255;
      }
    }
  });
}

/* ── Mapas de normales ───────────────────────────────────────────────
   Un mapa de relieve (bumpMap) obliga a la GPU a derivar la pendiente
   por diferencias de la textura en cada píxel; un mapa de NORMALES la
   lleva ya calculada y con más precisión, así que el microrrelieve se
   ve firme en vez de emborronado, y además cuesta menos. Se generan a
   partir del mismo campo de altura por Sobel, de modo que relieve y
   normales no pueden discrepar. */

function heightToNormal(THREE, height, strength) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = SIZE;
  const ctx = cv.getContext("2d");
  const img = ctx.createImageData(SIZE, SIZE);
  const d = img.data;
  const at = (x, y) => height(((x % SIZE) + SIZE) % SIZE, ((y % SIZE) + SIZE) % SIZE);

  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      // Sobel: pendiente en X y en Y del campo de altura
      const dx = (at(x + 1, y - 1) + 2 * at(x + 1, y) + at(x + 1, y + 1))
               - (at(x - 1, y - 1) + 2 * at(x - 1, y) + at(x - 1, y + 1));
      const dy = (at(x - 1, y + 1) + 2 * at(x, y + 1) + at(x + 1, y + 1))
               - (at(x - 1, y - 1) + 2 * at(x, y - 1) + at(x + 1, y - 1));
      let nx = -dx * strength, ny = -dy * strength, nz = 1;
      const len = Math.hypot(nx, ny, nz) || 1;
      nx /= len; ny /= len; nz /= len;
      const i = (y * SIZE + x) * 4;
      d[i] = Math.round((nx * 0.5 + 0.5) * 255);
      d[i + 1] = Math.round((ny * 0.5 + 0.5) * 255);
      d[i + 2] = Math.round((nz * 0.5 + 0.5) * 255);
      d[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  return tex;
}

/** Normales del esmalte: perikimatíes en la corona, grano en la raíz. */
export function enamelNormalTexture(THREE) {
  const noise = makeNoise(7717);
  return heightToNormal(THREE, (x, y) => {
    const v = 1 - y / (SIZE - 1);
    const isCrown = Math.min(1, Math.max(0, (v - 0.30) / 0.12));
    const n = fbm(noise, (x / SIZE) * 11, (y / SIZE) * 11, 3);
    /* Las perikimatíes son surcos de micras: a la escala a la que se ve
       una arcada completa deben insinuarse, no dibujar rayas. Con
       amplitud y frecuencia altas el esmalte se veía acanalado, como
       pana. La mayor parte del relieve la aporta el grano irregular. */
    const waves = Math.sin(v * 55 + n * 5) * 0.5 + 0.5;
    return isCrown
      ? 0.5 + (waves - 0.5) * 0.05 + (n - 0.5) * 0.09
      : 0.5 + (n - 0.5) * 0.45;
  }, 1.1);
}

/** Normales de la encía: punteado de cáscara de naranja en la adherida. */
export function gingivaNormalTexture(THREE) {
  const noise = makeNoise(31337);
  return heightToNormal(THREE, (x, y) => {
    const v = y / (SIZE - 1);
    const band = Math.max(
      Math.exp(-((v - 0.18) ** 2) / 0.006),
      Math.exp(-((v - 0.84) ** 2) / 0.006),
    );
    const stipple = fbm(noise, (x / SIZE) * 30, (y / SIZE) * 30, 2);
    const grain = fbm(noise, (x / SIZE) * 6, (y / SIZE) * 6, 3);
    return 0.5 + (stipple - 0.5) * 0.75 * band + (grain - 0.5) * 0.12;
  }, 3.0);
}
