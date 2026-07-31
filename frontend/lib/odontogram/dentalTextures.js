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
 * Microrrelieve del diente: perikimatíes —las finas ondas horizontales
 * del esmalte— en la corona y grano irregular en la raíz.
 */
export function enamelBumpTexture(THREE) {
  const noise = makeNoise(7717);
  return canvasTexture(THREE, (d) => {
    for (let y = 0; y < SIZE; y++) {
      const v = 1 - y / (SIZE - 1);
      const isCrown = Math.min(1, Math.max(0, (v - 0.30) / 0.12));
      for (let x = 0; x < SIZE; x++) {
        const n = fbm(noise, (x / SIZE) * 11, (y / SIZE) * 11, 3);
        // Ondas horizontales moduladas por ruido: nunca líneas perfectas
        const waves = Math.sin(v * 150 + n * 5) * 0.5 + 0.5;
        const val = isCrown
          ? 0.5 + (waves - 0.5) * 0.16 + (n - 0.5) * 0.10
          : 0.5 + (n - 0.5) * 0.55;
        const c = Math.round(Math.min(1, Math.max(0, val)) * 255);
        const i = (y * SIZE + x) * 4;
        d[i] = d[i + 1] = d[i + 2] = c;
        d[i + 3] = 255;
      }
    }
  });
}

/**
 * Punteado gingival ("cáscara de naranja"): el rasgo que identifica una
 * encía adherida sana. Se concentra en las vertientes adheridas y se
 * desvanece hacia el margen y hacia la mucosa alveolar, que son lisas.
 */
export function gingivaBumpTexture(THREE) {
  const noise = makeNoise(31337);
  return canvasTexture(THREE, (d) => {
    for (let y = 0; y < SIZE; y++) {
      const v = y / (SIZE - 1);
      // Dos franjas adheridas: vestibular y lingual
      const band = Math.max(
        Math.exp(-((v - 0.18) ** 2) / 0.006),
        Math.exp(-((v - 0.84) ** 2) / 0.006),
      );
      for (let x = 0; x < SIZE; x++) {
        const stipple = fbm(noise, (x / SIZE) * 30, (y / SIZE) * 30, 2);
        const grain = fbm(noise, (x / SIZE) * 6, (y / SIZE) * 6, 3);
        const val = 0.5 + (stipple - 0.5) * 0.75 * band + (grain - 0.5) * 0.12;
        const c = Math.round(Math.min(1, Math.max(0, val)) * 255);
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
