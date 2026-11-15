import { test } from 'node:test';
import assert from 'node:assert/strict';
import { similarCasesCard, similarCasesBody } from '../src/ui/components/similar-cases.js';

// Forma de GET /api/v1/patients/{id}/similar (backend/app/knn/service.py), reducida a 3 variables.
const features = [
  { key: 'age_years', label: 'Edad', group: 'context', weight: 3, unit: 'años', decimals: 0, kind: 'number' },
  { key: 'current_smoker', label: 'Fumador', group: 'context', weight: 2, unit: '', decimals: 0, kind: 'bool' },
  { key: 'systolic_trend', label: 'PA sistólica', group: 'trend', weight: 1.5, unit: 'mmHg/año', decimals: 1, kind: 'number' }
];
const neighbor = (rank, outcome, differences) => ({
  rank, label: 'Caso ' + rank, distance: rank, similarity: 50 - rank, exam: { period: 2, date: '2019-01-01' },
  values: { age_years: 55 + rank, current_smoker: 1, systolic_trend: null }, differences, outcome
});
const data = {
  mode: 'without_latest', k: 2, referenceTime: '2019-06-01', latestTestTime: '2025-09-03', features,
  patient: { values: { age_years: 56, current_smoker: 1, systolic_trend: 2.5 } },
  neighbors: [
    neighbor(1, { cvd: { status: 'event', years: 4.2 }, death: { status: 'none', years: 20 } }, { age_years: 0.1, current_smoker: 0, systolic_trend: null }),
    neighbor(2, { cvd: { status: 'none', years: 18 }, death: { status: 'before' } }, { age_years: 1.4, current_smoker: 0, systolic_trend: null })
  ],
  summary: { cvdEvents: 1, deaths: 0, withOutcome: 2 }
};

test('la tabla compara al paciente con cada caso y muestra cómo acabó', () => {
  const html = similarCasesBody({ data });
  assert.match(html, /Este paciente/);
  assert.match(html, /Caso 1/);
  assert.match(html, /Caso 2/);
  assert.match(html, /Sí <small>a los 4,2 años/);          // evento cardiovascular
  assert.match(html, /No <small>18,0 años/);               // sin evento, seguimiento
  assert.match(html, /Previo/);
  assert.match(html, /\+2,5/);                              // tendencia con signo
  assert.match(html, /<strong>1 de 2<\/strong> casos parecidos/);
  assert.match(html, /knn-close/);                          // edad casi igual
  assert.match(html, /knn-far/);                            // edad > 1 DE
  assert.match(html, /knn-missing/);                        // tendencia ausente: sin color
  assert.match(html, /antes de su última prueba/);
});

test('la tarjeta marca el modo elegido y muestra carga y errores', () => {
  assert.match(similarCasesCard(true, { loading: true }), /data-latest="true" aria-pressed="true"/);
  assert.match(similarCasesCard(false, { loading: true }), /Buscando casos parecidos/);
  assert.match(similarCasesBody({ error: 'Sin datos <b>' }), /Sin datos &lt;b&gt;/);
});
