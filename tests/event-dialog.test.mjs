import { test } from 'node:test';
import assert from 'node:assert/strict';
import { eventBody } from '../src/ui/dialogs/patient-dialogs.js';

// Forma de GET /api/v1/patients/{id}/events (backend/app/patients_service.py)
const blood = {
  id: 'b', date: '2025-09-03', title: 'Analítica de sangre', type: 'Analítica', testKind: 'blood', icon: 'flask',
  description: 'Informe del laboratorio, nº de petición 2448-3', documentId: 'doc-1',
  results: [{ field: 'glucose', label: 'Glucosa', value: 92, unit: 'mg/dL', decimals: 0 },
            { field: 'hba1c', label: 'HbA1c', value: 5.6, unit: '%', decimals: 1 }]
};
const vitals = {
  id: 'v', date: '2025-09-03', title: 'Presión arterial y constantes', type: 'Constantes', testKind: 'vitals', icon: 'heart',
  description: '', documentId: null,
  results: [{ field: 'systolic', label: 'PA sistólica', value: 121, unit: 'mmHg', decimals: 0 }]
};
const urine = { ...vitals, id: 'u', title: 'Prueba de orina', testKind: 'urine',
  results: [{ field: 'acr', label: 'Albuminuria (ACR)', value: 9, unit: 'mg/g', decimals: 0 }] };

test('la analítica muestra solo sus resultados y el PDF', () => {
  const html = eventBody(blood, 'Víctor');
  assert.match(html, /Glucosa/);
  assert.match(html, /5,6/);
  assert.doesNotMatch(html, /PA sistólica/);
  assert.match(html, /Ver informe del laboratorio \(PDF\)/);
  assert.match(html, /\/api\/v1\/documents\/doc-1\/content/);
});

test('tensión y orina muestran sus valores sin PDF', () => {
  for (const [event, value, absent] of [[vitals, /PA sistólica/, /Glucosa/], [urine, /Albuminuria/, /PA sistólica/]]) {
    const html = eventBody(event, 'Víctor');
    assert.match(html, value);
    assert.doesNotMatch(html, absent);
    assert.doesNotMatch(html, /Ver informe/);
  }
  assert.match(eventBody(vitals, 'Víctor'), /Datos del estudio de Framingham/);
  assert.match(eventBody(urine, 'Víctor'), /sintético/);
});
