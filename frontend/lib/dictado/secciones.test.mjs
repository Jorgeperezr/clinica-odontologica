// Pruebas del orden por palabras clave. Sin dependencias:
//   node --test frontend/lib/dictado/*.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { aTextoNota, aplicarPuntuacion, detectarSeccion, organizarDictado } from "./secciones.mjs";

test("cada palabra clave al abrir la frase cambia de sección", () => {
  const s = organizarDictado([
    "Motivo dolor al masticar en el lado derecho",
    "Hallazgos caries oclusal en la 46",
    "procedimiento resina compuesta",
    "Indicaciones no masticar por ese lado durante dos horas",
  ]);
  assert.equal(s.motivo, "Dolor al masticar en el lado derecho");
  assert.equal(s.hallazgos, "Caries oclusal en la 46");
  assert.equal(s.procedimiento, "Resina compuesta");
  assert.equal(s.indicaciones, "No masticar por ese lado durante dos horas");
});

test("la palabra clave a mitad de frase NO cambia de sección", () => {
  const s = organizarDictado(["Hallazgos el motivo de la molestia es una fisura"]);
  assert.equal(s.hallazgos, "El motivo de la molestia es una fisura");
  assert.equal(s.motivo, "");
});

test("sin palabra clave al empezar, va al motivo; las frases sin clave siguen en la sección actual", () => {
  const s = organizarDictado(["dolor desde ayer", "hallazgos gingivitis", "sangrado al sondaje"]);
  assert.equal(s.motivo, "Dolor desde ayer");
  assert.equal(s.hallazgos, "Gingivitis sangrado al sondaje");
});

test("tildes, mayúsculas y variantes del disparador", () => {
  assert.equal(detectarSeccion("INDICACIÓN enjuague con clorhexidina").seccion, "indicaciones");
  assert.equal(detectarSeccion("Motivo de consulta control").resto, "control");
  assert.equal(detectarSeccion("tratamiento realizado profilaxis").seccion, "procedimiento");
  assert.equal(detectarSeccion("hallazgos dos puntos nada relevante").resto, "nada relevante");
  assert.equal(detectarSeccion("el paciente refiere dolor"), null);
});

test("puntuación dictada, pero «punto» a secas se respeta", () => {
  assert.equal(aplicarPuntuacion("caries en la 46 punto y seguido sin dolor"), "caries en la 46. Sin dolor");
  assert.equal(aplicarPuntuacion("ajustar punto de contacto"), "ajustar punto de contacto");
  assert.equal(aplicarPuntuacion("uno punto y aparte dos"), "uno.\nDos");
});

test("la nota solo lleva las secciones con contenido", () => {
  const nota = aTextoNota(organizarDictado(["motivo control", "indicaciones cepillado tres veces al día"]));
  assert.equal(nota, "Motivo: Control\nIndicaciones: Cepillado tres veces al día");
});
