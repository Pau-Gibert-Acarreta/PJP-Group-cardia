import { test } from 'node:test';
import assert from 'node:assert/strict';
import { demoPatients as patients } from '../src/data/demo/patients.js';
import { selectPatients } from '../src/domain/patient-filters.js';
import { riskLevel } from '../src/domain/risk.js';
test('las fronteras del semáforo de demo son consistentes', () => {
  assert.equal(riskLevel(9.9), 'low'); assert.equal(riskLevel(10), 'medium');
  assert.equal(riskLevel(19.9), 'medium'); assert.equal(riskLevel(20), 'high');
});
test('búsqueda sin tildes por nombre e identificador', () => {
  assert.equal(selectPatients(patients, { search: 'maria garcia' })[0].id, 'p001');
  assert.equal(selectPatients(patients, { search: 'DEMO-10024' })[0].id, 'p024');
});
test('los filtros se combinan y ordenan sin modificar la lista original', () => {
  const before = patients.map(p => p.id);
  const result = selectPatients(patients, { risk: 'high', sex: 'Mujer', condition: 'Diabetes tipo 2', age: '65plus', sort: 'risk-asc' });
  assert.deepEqual(result.map(p => p.id), ['p001']);
  assert.deepEqual(patients.map(p => p.id), before);
  assert.ok(selectPatients(patients, { followupOnly: true }).every(p => p.followup));
  assert.equal(selectPatients(patients, { search: 'no existe' }).length, 0);
});
test('los perfiles tienen datos y eventos propios consistentes', () => {
  assert.equal(new Set(patients.map(p => p.id)).size, patients.length);
  for (const p of patients) {
    assert.ok(p.risk >= 0 && p.risk <= 100);
    assert.equal(p.events.at(-1).date, p.lastTest);
    assert.equal(p.history.ldl.at(-1), p.metrics.ldl);
    assert.equal(p.history.risk.at(-1), p.risk);
    assert.equal(p.history.pressure.at(-1), p.metrics.systolic);
  }
});

test('el ajuste clínico cambia la clasificación final pero no la probabilidad', async () => {
  const { effectiveRiskLevel, isRiskOverridden } = await import('../src/domain/risk.js');
  const base = { id: 'x', risk: 32.4 };
  assert.equal(effectiveRiskLevel(base), 'high');
  assert.equal(isRiskOverridden(base), false);
  const adjusted = { ...base, riskOverride: { level: 'medium', reason: 'AMPA en rango', date: '2026-11-14T10:00:00Z' } };
  assert.equal(effectiveRiskLevel(adjusted), 'medium');
  assert.equal(adjusted.risk, 32.4);
  assert.equal(isRiskOverridden(adjusted), true);
  assert.equal(effectiveRiskLevel({ ...base, riskOverride: { level: 'muy alto' } }), 'high', 'un nivel desconocido se ignora');
});
test('los filtros de riesgo usan la clasificación final y el orden sigue la probabilidad', () => {
  const items = patients.map(p => p.id === 'p001' ? { ...p, riskOverride: { level: 'low', reason: 'x', date: '2026-11-14' } } : p);
  assert.ok(!selectPatients(items, { risk: 'high' }).some(p => p.id === 'p001'));
  assert.ok(selectPatients(items, { risk: 'low' }).some(p => p.id === 'p001'));
  assert.equal(selectPatients(items, {})[0].id, 'p001');
});
