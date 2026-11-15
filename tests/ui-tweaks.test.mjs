import { test } from 'node:test';
import assert from 'node:assert/strict';
import { kdigoRisk } from '../src/domain/kdigo.js';
import { today } from '../src/ui/views/patient-list.js';

test('KDIGO: mapa de riesgo filtrado × albuminuria', () => {
  // [eGFR, ACR, riesgo] en cada zona del mapa
  const cases = [
    [95, 10, 'low'], [70, 10, 'low'], [95, 100, 'moderate'], [70, 400, 'high'],
    [50, 10, 'moderate'], [50, 100, 'high'], [50, 400, 'very-high'],
    [35, 10, 'high'], [35, 100, 'very-high'],
    [20, 10, 'very-high'], [10, 10, 'very-high']
  ];
  for (const [egfr, acr, risk] of cases) assert.equal(kdigoRisk(egfr, acr), risk, `G ${egfr} · A ${acr}`);
  assert.equal(kdigoRisk(null, 10), null);
});

test('la fecha de la cabecera es la del día, en español', () => {
  assert.equal(today(new Date(2026, 10, 15)), '15 de noviembre de 2026');
  assert.equal(today(new Date(2027, 0, 3)), '3 de enero de 2027');
});
