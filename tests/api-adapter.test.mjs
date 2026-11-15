import { test } from 'node:test';
import assert from 'node:assert/strict';
import { toPatient, mergeDetail } from '../src/services/patient-adapter.js';
import { pageWindow } from '../src/ui/views/patient-list.js';

// Forma real de GET /api/v1/patients (backend/app/patients_service.py).
const apiItem = {
  id: '2448', cip: 'SYN0002448', firstName: 'Víctor', lastName: 'Torres Cortés', name: 'Víctor Torres Cortés',
  initials: 'VT', age: 52, sex: 'Hombre', sexCode: 'M', risk: 13.5, riskLevel: 'medium', effectiveRiskLevel: 'medium',
  riskOverride: null, followup: false, lastTest: '2025-09-03', conditions: ['Dislipidemia'], activeFindings: 0,
  measurements: {
    systolic: [{ value: 106, date: '2013-01-01', unit: 'mmHg' }, { value: 121, date: '2025-09-03', unit: 'mmHg' }],
    egfr: [{ value: 103, date: '2013-01-01', unit: 'mL/min/1,73 m²' }]
  }
};

test('el adaptador conserva los datos de la base de datos y el riesgo del modelo', () => {
  const p = toPatient(apiItem);
  assert.equal(p.id, '2448');
  assert.equal(p.name, 'Víctor Torres Cortés');
  assert.equal(p.sex, 'Hombre');
  assert.deepEqual(p.conditions, ['Dislipidemia']);
  assert.equal(p.measurements.systolic.length, 2);
  assert.equal(p.detailLoaded, false);
  assert.equal(p.risk, 13.5);                          // la predicción guardada, no una simulación
  assert.deepEqual(p.history.risk, [13.5]);
  assert.deepEqual(p.factors, []);                     // los factores SHAP llegan con la ficha
  assert.ok(['sage', 'sand', 'rose', 'blue'].includes(p.color));
});

test('sin predicción el riesgo queda vacío, no se inventa', () => {
  const p = toPatient({ ...apiItem, risk: null });
  assert.equal(p.risk, null);
  assert.deepEqual(p.history.risk, []);
});

test('la ficha añade contacto, eventos en orden cronológico y notas', () => {
  const p = toPatient(apiItem);
  mergeDetail(p, {
    ...apiItem, phone: '630 936 362', email: 'victor.torres.2448@example.test', followup: true,
    events: [
      { id: 'b', date: '2025-12-01T09:00:00Z', title: 'Nueva analítica', type: 'Laboratorio', eventType: 'laboratory', icon: 'flask', description: '' },
      { id: 'a', date: '2013-01-01', title: 'Presión arterial y constantes', type: 'Constantes', eventType: 'exploration', testKind: 'vitals', icon: 'heart', description: '' }
    ],
    notes: [{ id: 'n1', text: 'Hola', author: 'Dra. Carmen Vidal', date: '2025-12-01T10:00:00Z' }],
    risk: 13.5, history: { risk: [13.5] },
    factors: [{ label: 'Sexo', value: 'Hombre', weight: 100, direction: 'up' }]
  });
  assert.equal(p.detailLoaded, true);
  assert.equal(p.phone, '630 936 362');
  assert.equal(p.followup, true);
  assert.deepEqual(p.events.map(e => e.id), ['a', 'b']);
  assert.equal(p.events[1].date, '2025-12-01');           // día para formatDate
  assert.equal(p.events[1].time, '2025-12-01T09:00:00Z'); // instante para cruzar con mediciones
  assert.equal(p.notes.length, 1);
  assert.equal(p.factors[0].label, 'Sexo');
});

test('la paginación muestra una ventana de páginas', () => {
  assert.deepEqual(pageWindow(1, 3), [1, 2, 3]);
  assert.deepEqual(pageWindow(1, 555), [1, 2, 3, 'gap', 555]);
  assert.deepEqual(pageWindow(100, 555), [1, 'gap', 98, 99, 100, 101, 102, 'gap', 555]);
  assert.deepEqual(pageWindow(555, 555), [1, 'gap', 553, 554, 555]);
});
