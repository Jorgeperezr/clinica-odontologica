"use client";

/**
 * Curva de la arcada (Sprint 53).
 * ────────────────────────────────────────────────────────────────────
 * Una elipse parcial parametrizada POR LONGITUD DE ARCO. Es la pieza que
 * garantiza que dientes y encía compartan exactamente la misma línea:
 * antes las piezas se distribuían sobre una elipse y la encía era un
 * toro circular, así que la encía atravesaba unas piezas y dejaba otras
 * al aire.
 *
 * Parametrizar por longitud de arco —y no por ángulo— también permite
 * repartir las piezas según su ancho mesio-distal real: en una elipse,
 * pasos angulares iguales dan separaciones desiguales, que es lo que
 * hacía que los molares se solaparan y los incisivos se separaran.
 */

const LUT_STEPS = 240;

/**
 * @param radiusX  semieje mesio-distal (izquierda-derecha)
 * @param radiusZ  semieje antero-posterior (profundidad)
 * @param angFrom  ángulo inicial en radianes
 * @param angTo    ángulo final
 */
export function createArchCurve(radiusX, radiusZ, angFrom, angTo) {
  const point = (ang) => [-Math.cos(ang) * radiusX, Math.sin(ang) * radiusZ];

  // Tabla ángulo → longitud acumulada
  const angs = new Float64Array(LUT_STEPS + 1);
  const lens = new Float64Array(LUT_STEPS + 1);
  let acc = 0;
  let [px, pz] = point(angFrom);
  angs[0] = angFrom; lens[0] = 0;
  for (let i = 1; i <= LUT_STEPS; i++) {
    const ang = angFrom + ((angTo - angFrom) * i) / LUT_STEPS;
    const [x, z] = point(ang);
    acc += Math.hypot(x - px, z - pz);
    angs[i] = ang; lens[i] = acc;
    px = x; pz = z;
  }
  const total = acc;

  /** Ángulo correspondiente a una longitud de arco (interpolación lineal en la tabla). */
  function angleAtLength(l) {
    const target = Math.max(0, Math.min(total, l));
    let lo = 0, hi = LUT_STEPS;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (lens[mid] <= target) lo = mid; else hi = mid;
    }
    const span = lens[hi] - lens[lo] || 1;
    const f = (target - lens[lo]) / span;
    return angs[lo] + (angs[hi] - angs[lo]) * f;
  }

  return {
    total,
    /** Punto [x, z] a la longitud de arco l. */
    pointAtLength(l) {
      return point(angleAtLength(l));
    },
    /**
     * Marco local a la longitud l: punto, tangente (sentido de la
     * arcada) y normal exterior (hacia vestibular).
     */
    frameAtLength(l) {
      const d = Math.max(total * 0.002, 0.01);
      const a = point(angleAtLength(Math.max(0, l - d)));
      const b = point(angleAtLength(Math.min(total, l + d)));
      let tx = b[0] - a[0], tz = b[1] - a[1];
      const len = Math.hypot(tx, tz) || 1;
      tx /= len; tz /= len;
      const [x, z] = point(angleAtLength(l));
      // Normal exterior: perpendicular a la tangente, alejándose del centro
      let nx = tz, nz = -tx;
      if (nx * x + nz * z < 0) { nx = -nx; nz = -nz; }
      return { x, z, tx, tz, nx, nz };
    },
  };
}

/**
 * Reparte piezas a lo largo de la curva en proporción a su ancho
 * mesio-distal, dejando una holgura uniforme. Devuelve, por pieza, su
 * posición de arco y su marco local.
 *
 * @param widths  ancho mesio-distal de cada pieza, en orden de arcada
 * @param gap     holgura entre piezas contiguas, en unidades de escena
 */
export function distributeAlongArch(curve, widths, gap = 0.03) {
  const span = widths.reduce((s, w) => s + w, 0) + gap * (widths.length - 1);
  // Si las piezas no caben, se comprimen por igual antes que solaparse
  const k = span > curve.total ? curve.total / span : 1;
  const margin = (curve.total - span * k) / 2;

  const out = [];
  let cursor = margin;
  widths.forEach((w) => {
    const center = cursor + (w * k) / 2;
    out.push({ length: center, ...curve.frameAtLength(center) });
    cursor += w * k + gap * k;
  });
  return out;
}
