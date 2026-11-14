// Contenido clínico de src/config/finding-rules.json (v2). Ver docs/finding-rules.md.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateClinicalConfig } from '../src/domain/clinical-config.js';
import { evaluateFindings } from '../src/domain/findings.js';

const readJSON = file => JSON.parse(readFileSync(new URL(file, import.meta.url), 'utf8'));
const config = readJSON('../src/config/indicators.json');
const rules = readJSON('../src/config/finding-rules.json');

const at = (value, date) => ({ value, date });
const ids = measurements => evaluateFindings({ measurements }, config, rules).map(f => f.id);

test('las reglas v2 son válidas para el motor', () => {
  assert.equal(rules.version, 2);
  assert.equal(validateClinicalConfig(config, rules), true);
});

test('umbrales absolutos: hipertensión grado 3 (inclusivos)', () => {
  assert.deepEqual(ids({ systolic: [at(121, '2013-01-01'), at(180, '2025-09-03')] }), ['presion-sistolica-grado-3']);
  assert.deepEqual(ids({ systolic: [at(121, '2013-01-01'), at(179, '2025-09-03')] }), []);
  assert.deepEqual(ids({ diastolic: [at(80, '2013-01-01'), at(110, '2025-09-03')] }), ['presion-diastolica-grado-3']);
});

test('umbrales absolutos sin límite de tiempo: funcionan con exámenes separados años', () => {
  const found = ids({
    total_cholesterol: [at(250, '2013-01-01'), at(310, '2025-09-03')],
    hdl_cholesterol: [at(45, '2013-01-01'), at(39, '2025-09-03')],
    egfr: [at(32, '2013-01-01'), at(29, '2025-09-03')] // −9 %: solo el umbral absoluto
  });
  assert.deepEqual(found, ['colesterol-total-extremo', 'hdl-bajo', 'egfr-menor-30']);
});

test('HbA1c: rango diabético y > 10 % se acumulan', () => {
  assert.deepEqual(ids({ hba1c: [at(6, '2026-01-01'), at(6.5, '2026-06-01')] }), ['hba1c-rango-diabetico']);
  assert.deepEqual(ids({ hba1c: [at(8, '2026-01-01'), at(10.1, '2026-06-01')] }), ['hba1c-rango-diabetico', 'hba1c-hiperglucemia-severa']);
  assert.deepEqual(ids({ hba1c: [at(8, '2026-01-01'), at(10, '2026-06-01')] }), ['hba1c-rango-diabetico']);
});

test('ACR: A3 y duplicación (exige ACR >= 30)', () => {
  assert.deepEqual(ids({ acr: [at(100, '2026-01-01'), at(301, '2026-06-01')] }), ['acr-albuminuria-a3', 'acr-duplicacion']);
  assert.deepEqual(ids({ acr: [at(10, '2026-01-01'), at(25, '2026-06-01')] }), []); // +150 % pero < 30
  assert.deepEqual(ids({ acr: [at(20, '2026-01-01'), at(40, '2026-06-01')] }), ['acr-duplicacion']);
});

test('eGFR: descenso estrictamente mayor del 20 %', () => {
  assert.deepEqual(ids({ egfr: [at(100, '2013-01-01'), at(79, '2025-09-03')] }), ['egfr-descenso-significativo']);
  assert.deepEqual(ids({ egfr: [at(100, '2013-01-01'), at(80, '2025-09-03')] }), []);
});

test('AKI: solo con mediciones cercanas en el tiempo', () => {
  assert.deepEqual(ids({ serum_creatinine: [at(1, '2026-11-01T08:00:00Z'), at(1.3, '2026-11-03T08:00:00Z')] }), ['aki-creatinina-048h']);
  assert.deepEqual(ids({ serum_creatinine: [at(1, '2026-11-01T08:00:00Z'), at(1.3, '2026-11-03T09:00:00Z')] }), []); // 49 h
  assert.deepEqual(ids({ serum_creatinine: [at(1, '2026-11-01'), at(1.5, '2026-11-08')] }), ['aki-creatinina-150-7dias']);
  assert.deepEqual(ids({ serum_creatinine: [at(1, '2013-01-01'), at(2, '2025-09-03')] }), []); // años: no es AKI
});
