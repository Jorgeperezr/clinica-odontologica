import assert from "node:assert/strict";
import { test } from "node:test";

import { calcularIndicadores, decimal } from "./indicadoresBucales.mjs";

const todos = (placa, calculo, gingivitis) =>
  Object.fromEntries(["16", "11", "26", "36", "31", "46"].map((k) => [k, { placa, calculo, gingivitis }]));

test("boca limpia: IHO-S 0, bueno", () => {
  const r = calcularIndicadores(todos(0, 0, 0));
  assert.equal(r.ihos.indice, 0);
  assert.equal(r.ihos.nivel, "bueno");
  assert.equal(r.completos, 6);
  assert.equal(r.gingivitis.porcentaje, 0);
});

test("los umbrales de Greene y Vermillion", () => {
  // placa 1 y cálculo 1 en los seis: IDB-S 1,0 (regular) + ICS 1,0 = 2,0 regular
  const r = calcularIndicadores(todos(1, 1, 1));
  assert.deepEqual([r.placa.nivel, r.calculo.nivel, r.ihos.indice, r.ihos.nivel],
                   ["regular", "regular", 2, "regular"]);
  assert.equal(r.gingivitis.porcentaje, 100);
  const malo = calcularIndicadores(todos(3, 2, 1));
  assert.deepEqual([malo.ihos.indice, malo.ihos.nivel], [5, "malo"]);
  assert.equal(calcularIndicadores(todos(1, 0, 0)).ihos.nivel, "bueno");   // 1,0
});

test("se promedia sobre los sextantes registrados, no sobre seis", () => {
  // Solo dos sextantes: suma 4 de placa → 2,0, no 0,7.
  const r = calcularIndicadores({ "16": { placa: 2, calculo: 0 }, "11": { placa: 2, calculo: 0 } });
  assert.equal(r.placa.indice, 2);
  assert.equal(r.placa.nivel, "malo");
  assert.equal(r.completos, 0);          // sin gingivitis no están completos
});

test("sin datos no inventa un resultado", () => {
  const r = calcularIndicadores({});
  assert.equal(r.ihos.indice, null);
  assert.equal(r.ihos.nivel, null);
  assert.equal(r.gingivitis.porcentaje, null);
  // Con placa pero sin cálculo tampoco hay IHO-S.
  assert.equal(calcularIndicadores({ "16": { placa: 1 } }).ihos.indice, null);
});

test("el cero cuenta como dato, el vacío no", () => {
  const r = calcularIndicadores({ "16": { placa: 0, calculo: 0, gingivitis: 0 }, "11": { placa: "" } });
  assert.equal(r.placa.sextantes, 1);
});

test("coma decimal", () => {
  assert.equal(decimal(1.25), "1,3");
  assert.equal(decimal(null), "—");
});
