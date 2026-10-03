/**
 * Fechas «de calendario» (AAAA-MM-DD) en la hora del equipo, no en UTC.
 *
 * `new Date().toISOString().slice(0, 10)` da la fecha en UTC. En Ecuador
 * (UTC−5), a partir de las 19:00 eso ya es el día siguiente: una
 * evolución, un pago o un diagnóstico registrados por la tarde quedaban
 * con fecha de mañana, y la receta impresa decía 30/09 arriba y 29/09 en
 * el pie. Estaba en doce sitios del panel.
 */

/** AAAA-MM-DD de una fecha, con el año, mes y día del equipo. */
export function fechaISO(d = new Date()) {
  const dos = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
}

/** Hoy, en el calendario del equipo. */
export function hoyISO() {
  return fechaISO(new Date());
}
