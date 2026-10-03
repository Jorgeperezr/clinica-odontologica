/**
 * Ordenar un dictado en las secciones de la nota clínica, SIN IA.
 * ────────────────────────────────────────────────────────────────────
 * El doctor dice la palabra clave de la sección y luego su contenido:
 *
 *     «Motivo… dolor al masticar en el lado derecho»
 *     «Hallazgos… caries oclusal en la 46»
 *     «Procedimiento… resina compuesta»
 *     «Indicaciones… no masticar por ese lado durante dos horas»
 *
 * Regla que evita falsos cambios de sección: la palabra clave solo
 * cuenta si ABRE una frase, es decir, si va justo después de una pausa
 * (el reconocedor entrega el dictado por frases). «El motivo de la
 * molestia es…» a mitad de frase se queda donde estaba.
 *
 * Sin dependencias y sin tocar el DOM: se prueba con `node --test`.
 */

export const SECCIONES = [
  { clave: "motivo", titulo: "Motivo", disparadores: ["motivo de consulta", "motivo de la consulta", "motivo"] },
  { clave: "hallazgos", titulo: "Hallazgos", disparadores: ["hallazgos", "hallazgo", "examen clínico", "exploración"] },
  { clave: "procedimiento", titulo: "Procedimiento", disparadores: ["procedimientos", "procedimiento", "tratamiento realizado"] },
  { clave: "indicaciones", titulo: "Indicaciones", disparadores: ["indicaciones", "indicación", "recomendaciones"] },
];

/** Minúsculas y sin tildes, para comparar lo que dice el reconocedor. */
export function normalizar(texto) {
  return (texto || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
}

/*
 * Puntuación dictada. Solo las fórmulas explícitas: «punto» a secas no,
 * porque en odontología es una palabra corriente («punto de contacto»).
 */
const PUNTUACION = [
  [/\s*\bpunto y aparte\b\s*/gi, ".\n"],
  [/\s*\bnueva l[ií]nea\b\s*/gi, "\n"],
  [/\s*\bpunto y seguido\b\s*/gi, ". "],
  [/\s*\bdos puntos\b\s*/gi, ": "],
];

export function aplicarPuntuacion(texto) {
  let t = texto;
  for (const [patron, signo] of PUNTUACION) t = t.replace(patron, signo);
  return t.replace(/[ \t]+/g, " ").replace(/ +\n/g, "\n").trim()
    // Mayúscula tras un punto dictado, como se escribiría a mano.
    .replace(/([.\n]\s*)(\p{Ll})/gu, (_, antes, letra) => antes + letra.toUpperCase());
}

/**
 * ¿La frase empieza por la palabra clave de una sección? Devuelve la
 * sección y el resto de la frase, o null.
 */
export function detectarSeccion(frase) {
  const limpia = normalizar(frase).replace(/^[\s,.:;-]+/, "");
  for (const s of SECCIONES) {
    for (const d of s.disparadores) {
      const n = normalizar(d);
      if (limpia === n || limpia.startsWith(`${n} `) || limpia.startsWith(`${n}:`) || limpia.startsWith(`${n},`)) {
        // Se corta sobre la frase ORIGINAL para conservar mayúsculas y
        // tildes del contenido: se cuentan las palabras del disparador.
        const palabras = n.split(" ").length;
        const resto = frase.trim().split(/\s+/).slice(palabras).join(" ")
          .replace(/^(dos puntos\s*)/i, "").replace(/^[\s,.:;-]+/, "");
        return { seccion: s.clave, resto };
      }
    }
  }
  return null;
}

/**
 * Reparte las frases dictadas entre las secciones.
 *
 * @param frases   frases en el orden dictado (cada una, tras una pausa)
 * @param inicial  sección en la que se empieza si la primera frase no
 *                 dice ninguna (por defecto, «motivo»)
 * @returns { motivo, hallazgos, procedimiento, indicaciones } en texto
 */
export function organizarDictado(frases, inicial = "motivo") {
  const partes = Object.fromEntries(SECCIONES.map((s) => [s.clave, []]));
  let actual = inicial;
  for (const bruta of frases) {
    const frase = (bruta || "").trim();
    if (!frase) continue;
    const d = detectarSeccion(frase);
    if (d) {
      actual = d.seccion;
      if (d.resto) partes[actual].push(d.resto);
    } else {
      partes[actual].push(frase);
    }
  }
  return Object.fromEntries(Object.entries(partes).map(([k, v]) => [k, capitalizar(aplicarPuntuacion(v.join(" ")))]));
}

function capitalizar(t) {
  return t ? t[0].toUpperCase() + t.slice(1) : t;
}

/** Las secciones como texto de la nota: solo las que tienen contenido. */
export function aTextoNota(secciones) {
  return SECCIONES
    .filter((s) => secciones[s.clave])
    .map((s) => `${s.titulo}: ${secciones[s.clave]}`)
    .join("\n");
}
