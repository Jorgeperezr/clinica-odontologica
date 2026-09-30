/**
 * Índice de higiene oral simplificado (IHO-S, Greene y Vermillion) a
 * partir de los datos del literal I del formulario 033.
 *
 * Por cada sextante se anota placa (0-3), cálculo (0-3) y gingivitis
 * (0-1) de su pieza índice. El formulario solo pedía las sumas; lo que
 * el profesional necesita leer es el índice y si es bueno o malo, y eso
 * no lo calculaba nadie. Aquí, sin tocar lo que se guarda.
 *
 *   IDB-S (placa)   = suma de placa   / sextantes registrados   (0 a 3)
 *   ICS   (cálculo) = suma de cálculo / sextantes registrados   (0 a 3)
 *   IHO-S           = IDB-S + ICS                              (0 a 6)
 *
 * Escalas de interpretación habituales:
 *   IDB-S e ICS: 0,0-0,6 bueno · 0,7-1,8 regular · 1,9-3,0 malo
 *   IHO-S:       0,0-1,2 bueno · 1,3-3,0 regular · 3,1-6,0 malo
 */

// El formulario guarda cada sextante con la primera pieza como clave.
export const SEXTANTES = [
  { clave: "16", piezas: ["16", "17", "55"], nombre: "Superior derecho" },
  { clave: "11", piezas: ["11", "21", "51"], nombre: "Anterior superior" },
  { clave: "26", piezas: ["26", "27", "65"], nombre: "Superior izquierdo" },
  { clave: "36", piezas: ["36", "37", "75"], nombre: "Inferior izquierdo" },
  { clave: "31", piezas: ["31", "41", "71"], nombre: "Anterior inferior" },
  { clave: "46", piezas: ["46", "47", "85"], nombre: "Inferior derecho" },
];

const redondear = (n) => Math.round(n * 10) / 10;

function nivel(valor, bueno, regular) {
  if (valor === null) return null;
  if (valor <= bueno) return "bueno";
  if (valor <= regular) return "regular";
  return "malo";
}

const esNumero = (v) => v !== null && v !== undefined && v !== "" && !Number.isNaN(Number(v));

/** Índices y su interpretación. `null` donde todavía no hay datos. */
export function calcularIndicadores(higiene = {}) {
  let placa = 0, calculo = 0, conPlaca = 0, conCalculo = 0, gingivitis = 0, conGingivitis = 0;
  for (const { clave } of SEXTANTES) {
    const h = higiene[clave] || {};
    if (esNumero(h.placa)) { placa += Number(h.placa); conPlaca += 1; }
    if (esNumero(h.calculo)) { calculo += Number(h.calculo); conCalculo += 1; }
    if (esNumero(h.gingivitis)) { gingivitis += Number(h.gingivitis); conGingivitis += 1; }
  }
  const idb = conPlaca ? redondear(placa / conPlaca) : null;
  const ics = conCalculo ? redondear(calculo / conCalculo) : null;
  // El IHO-S solo tiene sentido con los dos componentes.
  const ihos = idb !== null && ics !== null ? redondear(idb + ics) : null;
  return {
    placa: { suma: placa, sextantes: conPlaca, indice: idb, nivel: nivel(idb, 0.6, 1.8) },
    calculo: { suma: calculo, sextantes: conCalculo, indice: ics, nivel: nivel(ics, 0.6, 1.8) },
    ihos: { indice: ihos, nivel: nivel(ihos, 1.2, 3.0) },
    gingivitis: {
      positivos: gingivitis, sextantes: conGingivitis,
      porcentaje: conGingivitis ? Math.round((gingivitis / conGingivitis) * 100) : null,
    },
    completos: SEXTANTES.filter(({ clave }) => {
      const h = higiene[clave] || {};
      return esNumero(h.placa) && esNumero(h.calculo) && esNumero(h.gingivitis);
    }).length,
  };
}

/** Número con coma decimal, como se escribe en Ecuador. */
export function decimal(n) {
  return n === null || n === undefined ? "—" : n.toFixed(1).replace(".", ",");
}
