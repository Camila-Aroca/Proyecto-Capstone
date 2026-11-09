import { test } from "node:test";
import assert from "node:assert/strict";
import { resumirPropuestas } from "../src/propuestaCamas.ts";

const area = (codigo, aumento, base = 20) => ({
  nivel_cuidado_codigo: codigo,
  propuesta_camas: { aumento_dotacion: aumento, base_capacidad: base, ano_objetivo: 2027,
    motivo: aumento == null ? "Sin historia suficiente" : null },
});

test("total inicial suma aumentos por área, sin compensar con holgura de otra", () => {
  const r = resumirPropuestas([area(418, 7, 39), area(421, 0, 24)], 63);
  assert.equal(r.aumento, 7);
  assert.equal(r.capacidadPropuesta, 70);
  assert.equal(r.parcial, false);
  assert.equal(r.ano, 2027);
});

test("un hospital con una sola área tiene propuesta desde el inicio", () => {
  assert.equal(resumirPropuestas([area(418, 3)], 20).aumento, 3);
});

test("la falta de dotación hospitalaria usa las bases REM-20 ya calculadas", () => {
  const r = resumirPropuestas([area(418, 2, 19.5), area(421, 1, 12)], 31.5);
  assert.equal(r.aumento, 3);
  assert.equal(r.capacidadPropuesta, 34.5);
});

test("el subtotal respaldado se publica como parcial sin inventar ceros", () => {
  const r = resumirPropuestas([area(418, 4), area(420, null)], 40);
  assert.equal(r.aumento, 4);
  assert.equal(r.parcial, true);
  assert.equal(r.areasConPropuesta, 1);
  assert.equal(r.areasTotales, 2);
});

test("cero respaldado es una cifra; falta real de datos no es cero", () => {
  assert.equal(resumirPropuestas([area(418, 0)], 20).aumento, 0);
  assert.equal(resumirPropuestas([area(420, null)], 20).aumento, null);
  assert.equal(resumirPropuestas(null, 20).aumento, null);
});
