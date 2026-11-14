import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { demoPatients as patients } from '../src/data/demo/patients.js';
import { validateClinicalConfig } from '../src/domain/clinical-config.js';
import { loadClinicalConfig } from '../src/services/config-service.js';
import { getSeries, summarizeIndicator, getIndicatorRows } from '../src/domain/measurements.js';
import { evaluateFindings } from '../src/domain/findings.js';
import { kdigoCategory, patientKdigo } from '../src/domain/kdigo.js';
import { overviewHeader, overviewRow } from '../src/ui/components/overview-table.js';
import { indicatorTrend, renderIndicators } from '../src/ui/components/key-indicators.js';
import { renderFindings } from '../src/ui/components/findings-card.js';
const readJSON = file => JSON.parse(readFileSync(new URL(file, import.meta.url), 'utf8').replace(/^\uFEFF/, ''));
const config = readJSON('../src/config/indicators.json');
// Reglas v1 congeladas: prueban la semántica del motor, no el contenido clínico de src/config.
const rules = readJSON('./fixtures/finding-rules.v1.json');
const systolic = config.indicators.find(item => item.field === 'systolic');
const record = (value, date, unit) => ({ value, date, ...(unit ? { unit } : {}) });
const patient = measurements => ({ id: 'test', measurements });
const clone = value => structuredClone(value);

test('configuración real: ocho indicadores y referencias coherentes', () => {
  assert.equal(validateClinicalConfig(config, rules), true);
  assert.deepEqual(config.indicators.map(item => item.field), ['systolic', 'diastolic', 'total_cholesterol', 'hdl_cholesterol', 'hba1c', 'acr', 'serum_creatinine', 'egfr']);
  assert.deepEqual(config.overviewFields, ['egfr', 'acr', 'systolic', 'diastolic', 'hba1c']);
});

test('historial ordenado: valores válidos, ceros, fechas imposibles y duplicados', () => {
  const p = patient({ systolic: [
    record(148, '2026-11-10'), record(125, '2026-02-12'), record(null, '2026-10-10'),
    record('140', '2026-10-11'), record(999, 'no es fecha'), record(999, '2026-02-30'),
    record(999, '2026-09-12', 'kPa'), record(0, '2026-01-12'),
    record(128, '2026-02-12T00:00:00Z'), record(Infinity, '2026-11-11')
  ] });
  const original = clone(p);
  assert.deepEqual(getSeries(p, systolic).map(item => item.value), [0, 128, 148]);
  assert.deepEqual(p, original);
  const summary = summarizeIndicator(p, systolic);
  assert.equal(summary.latest.date, '2026-11-10');
  assert.equal(summary.previous.value, 128);
  assert.equal(summary.delta, 20);
  assert.equal(summary.min, 0);
  assert.equal(summary.max, 148);
});

test('sin datos, un dato y serie constante no producen NaN ni cambios ficticios', () => {
  for (const series of [[], [record(120, '2026-11-01')], [record(120, '2026-08-01'), record(120, '2026-11-01')]]) {
    const p = patient({ systolic: series });
    const summary = summarizeIndicator(p, systolic);
    assert.equal(summary.delta, 0);
    const html = indicatorTrend(summary);
    assert.ok(!html.includes('NaN'));
    assert.ok(!html.includes('Infinity'));
    assert.equal(evaluateFindings(p, config, rules).length, 0);
  }
});

test('las dos últimas mediciones activan el umbral inclusivo, no el cambio histórico', () => {
  const p = patient({ systolic: [record(80, '2026-01-01'), record(128, '2026-08-07'), record(143, '2026-11-10')] });
  const findings = evaluateFindings(p, config, rules);
  assert.deepEqual(findings.map(item => item.id), ['systolic-rise']);
  assert.equal(findings[0].indicator.previous.value, 128);
  assert.equal(findings[0].indicator.latest.value, 143);
  const html = renderFindings(p, config, rules);
  assert.match(html, /Aumento de PA sistólica/);
  assert.match(html, /128/);
  assert.match(html, /143/);
  assert.match(html, /2026-08-07/);
  assert.match(html, /2026-11-10/);
});

test('las comparaciones decimales no pierden el umbral por precisión binaria', () => {
  const p = patient({ hba1c: [record(6.7, '2026-10-01'), record(7.2, '2026-11-01')], serum_creatinine: [record(1.1, '2026-10-01'), record(1.4, '2026-11-01')] });
  assert.deepEqual(evaluateFindings(p, config, rules).map(item => item.id), ['hba1c-rise', 'creatinine-rise']);
});

test('porcentajes negativos, combinación AND, intervalo y reglas desactivadas', () => {
  const p = patient({
    egfr: [record(80, '2026-10-01'), record(64, '2026-11-01')],
    acr: [record(10, '2026-10-01'), record(15, '2026-11-01')],
    systolic: [record(100, '2025-01-01'), record(150, '2026-11-01')]
  });
  assert.deepEqual(evaluateFindings(p, config, rules).map(item => item.id), ['egfr-fall']);
  const disabled = clone(rules); disabled.rules.find(item => item.id === 'egfr-fall').enabled = false;
  assert.equal(evaluateFindings(p, config, disabled).length, 0);
});

test('porcentaje respecto a cero no genera Infinity y los valores absolutos siguen funcionando', () => {
  const p = patient({ acr: [record(0, '2026-10-01'), record(50, '2026-11-01')] });
  const summary = summarizeIndicator(p, config.indicators.find(item => item.field === 'acr'));
  assert.equal(summary.percentChange, null);
  assert.equal(summary.delta, 50);
  assert.equal(evaluateFindings(p, config, rules).length, 0);
});

test('se añade una variable y una regla solo mediante configuración', () => {
  const custom = clone(config);
  custom.indicators.push({ field: 'future_db_column', label: 'Variable futura', unit: 'U/L', decimals: 1 });
  const customRules = { rules: [{ id: 'new-rule', enabled: true, field: 'future_db_column', title: 'Cambio nuevo', severity: 'attention', conditions: [{ metric: 'delta', operator: 'gte', value: 5 }] }] };
  assert.equal(validateClinicalConfig(custom, customRules), true);
  const p = patient({ future_db_column: [record(12, '2026-10-01'), record(18, '2026-11-01')] });
  assert.equal(getIndicatorRows(p, custom).at(-1).latest.value, 18);
  assert.match(renderIndicators(p, custom), /Variable futura/);
  assert.match(renderFindings(p, custom, customRules), /Cambio nuevo/);
});

test('se rechazan referencias, operadores y condiciones erróneas de configuración', () => {
  for (const change of [
    rule => rule.field = 'unknown_field',
    rule => rule.conditions[0].operator = 'constructor',
    rule => rule.conditions[0].metric = 'unknown',
    rule => rule.conditions[0].value = '15',
    rule => rule.conditions = [],
    rule => rule.maxIntervalDays = -1
  ]) {
    const invalid = clone(rules); change(invalid.rules[0]);
    assert.throws(() => validateClinicalConfig(config, invalid));
  }
  const invalid = clone(config); invalid.indicators.push(clone(invalid.indicators[0]));
  assert.throws(() => validateClinicalConfig(invalid, rules));
});

test('la minigráfica escala exactamente entre mínimo y máximo y maneja fechas reales', () => {
  const summary = summarizeIndicator(patient({ systolic: [record(100, '2026-01-01'), record(120, '2026-02-01'), record(140, '2026-11-01')] }), systolic);
  const html = indicatorTrend(summary);
  assert.match(html, /mín 100/); assert.match(html, /máx 140/);
  assert.match(html, /cx="5" cy="35"/); assert.match(html, /cx="143" cy="5"/);
});

test('categorías KDIGO: límites de eGFR y ACR, sin inventar valores ausentes', () => {
  for (const [value, expected] of [[90, 'G1'], [89.9, 'G2'], [60, 'G2'], [59.9, 'G3a'], [45, 'G3a'], [44.9, 'G3b'], [30, 'G3b'], [29.9, 'G4'], [15, 'G4'], [14.9, 'G5']]) assert.equal(kdigoCategory(value, 10), expected + ' · A1');
  assert.equal(kdigoCategory(68, 29.9), 'G2 · A1');
  assert.equal(kdigoCategory(68, 30), 'G2 · A2');
  assert.equal(kdigoCategory(68, 299.9), 'G2 · A2');
  assert.equal(kdigoCategory(68, 300), 'G2 · A3');
  for (const value of [null, undefined, NaN, -1, '68']) assert.equal(kdigoCategory(value, 42), null);
  assert.equal(patientKdigo(patient({}), config), null);
  const incompatible = clone(config); incompatible.indicators.find(item => item.field === 'acr').unit = 'mg/mmol';
  assert.equal(patientKdigo(patients[0], incompatible), null);
});

test('resumen y ficha utilizan los mismos valores, campos y fechas por paciente', () => {
  const header = overviewHeader(config, 'risk-desc');
  assert.ok(header.indexOf('Prob. riesgo') < header.indexOf('Paciente'));
  for (const label of ['KDIGO', 'eGFR', 'ACR', 'PA sistólica', 'PA diastólica', 'HbA1c', 'Fecha última']) assert.ok(header.includes(label));
  assert.equal(patientKdigo(patients[0], config), 'G2 · A2');
  for (const p of patients) {
    const rows = getIndicatorRows(p, config);
    assert.equal(rows.length, 8);
    assert.equal(rows.find(item => item.field === 'egfr').latest.value, p.metrics.egfr);
    assert.equal(rows.find(item => item.field === 'systolic').latest.value, p.metrics.systolic);
    assert.match(overviewRow(p, config), new RegExp(p.age + ' años · ' + p.sex));
    for (const html of [overviewRow(p, config), renderIndicators(p, config), renderFindings(p, config, rules)]) {
      assert.ok(!/NaN|Infinity|undefined/.test(html));
    }
  }
  assert.match(renderIndicators(patients[23], config), /Sin datos/);
  assert.match(renderIndicators(patients[23], config), /Sin valor anterior/);
  assert.equal(evaluateFindings(patients[0], config, rules).length, 3);
  assert.equal(evaluateFindings(patients[23], config, rules).length, 0);
});

test('etiquetas y títulos de configuración se escapan al generar HTML', () => {
  const custom = clone(config); custom.indicators[0].label = '<img onerror="alert(1)">';
  const html = renderIndicators(patients[0], custom);
  assert.ok(html.includes('&lt;img'));
  assert.ok(!html.includes('<img'));
});

test('carga de JSON local con errores explícitos, sin dependencia de una BD', async () => {
  const fetched = [];
  const result = await loadClinicalConfig(async url => {
    fetched.push(url.pathname);
    return { ok: true, json: async () => url.pathname.endsWith('indicators.json') ? config : rules };
  });
  assert.equal(result.config, config);
  assert.equal(fetched.length, 2);
  assert.ok(fetched.every(path => path.includes('/src/config/')));
  await assert.rejects(loadClinicalConfig(async () => ({ ok: false })), /No se ha podido cargar/);
});


test('la gráfica ampliable utiliza las mismas mediciones y fechas reales', async () => {
  const { chartData, chart } = await import('../src/ui/components/chart.js');
  const data = chartData(patients[0], { chart: 'pressure', period: '6' });
  assert.equal(data.values.at(-1), patients[0].metrics.systolic);
  assert.equal(data.values.at(-2), 128);
  assert.equal(data.values.length, 3);
  for (const p of [patient({}), patient({ systolic: [record(120, '2026-11-01')] })]) {
    const html = chart(p, { chart: 'pressure', period: '12' });
    assert.ok(!/NaN|Infinity|undefined/.test(html));
  }
});

