// node --test frontend/lib/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { fechaISO, hoyISO } from "./fechas.mjs";

test("a las 20:30 de Ecuador sigue siendo el mismo día", () => {
  // Se construye con la hora local del proceso: la prueba vale en
  // cualquier zona, que es justo lo que toISOString no respetaba.
  const tarde = new Date(2026, 8, 29, 20, 30);
  assert.equal(fechaISO(tarde), "2026-09-29");
  const casiMedianoche = new Date(2026, 11, 31, 23, 59);
  assert.equal(fechaISO(casiMedianoche), "2026-12-31");
});

test("meses y días de una cifra llevan cero", () => {
  assert.equal(fechaISO(new Date(2026, 0, 5, 9)), "2026-01-05");
});

test("hoy es la fecha local de ahora", () => {
  assert.equal(hoyISO(), fechaISO(new Date()));
});
