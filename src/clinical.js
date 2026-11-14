// Lógica de presentación y reglas sobre datos normalizados. Sin llamadas a BD ni a ML.
const conditionMetrics = new Set(['current', 'previous', 'delta', 'percent_change']);
const operators = {
  gt: (a, b) => a > b, gte: (a, b) => a >= b,
  lt: (a, b) => a < b, lte: (a, b) => a <= b, eq: (a, b) => a === b
};
export function validateClinicalConfig(config, ruleConfig) {
  if (!Array.isArray(config?.indicators) || !Array.isArray(ruleConfig?.rules)) throw new Error('La configuración debe incluir indicators y rules.');
  const fields = new Set();
  for (const indicator of config.indicators) {
    if (typeof indicator.field !== 'string' || !indicator.field.trim() || fields.has(indicator.field) ||
        typeof indicator.label !== 'string' || typeof indicator.unit !== 'string' ||
        !Number.isInteger(indicator.decimals) || indicator.decimals < 0 || indicator.decimals > 6) {
      throw new Error('Definición de indicador inválida o duplicada.');
    }
    fields.add(indicator.field);
  }
  if (!Array.isArray(config.overviewFields) || config.overviewFields.some(field => !fields.has(field)) ||
      !fields.has(config.kdigoFields?.egfr) || !fields.has(config.kdigoFields?.acr)) throw new Error('Campos de resumen o KDIGO desconocidos.');
  const ids = new Set();
  for (const rule of ruleConfig.rules) {
    if (typeof rule.id !== 'string' || !rule.id || ids.has(rule.id)) throw new Error('Identificador de regla inválido o duplicado.');
    ids.add(rule.id);
    if (rule.enabled === false) continue;
    if (!fields.has(rule.field) || typeof rule.title !== 'string' || !rule.title.trim() ||
        !['attention', 'warning'].includes(rule.severity) || !Array.isArray(rule.conditions) || !rule.conditions.length ||
        (rule.maxIntervalDays !== undefined && (!Number.isFinite(rule.maxIntervalDays) || rule.maxIntervalDays <= 0))) {
      throw new Error('Regla inválida: ' + rule.id);
    }
    for (const condition of rule.conditions) {
      if (!conditionMetrics.has(condition.metric) || !Object.hasOwn(operators, condition.operator) || !Number.isFinite(condition.value)) throw new Error('Condición inválida: ' + rule.id);
    }
  }
  return true;
}
export async function loadClinicalConfig(fetchFile = fetch) {
  const files = ['indicators.json', 'finding-rules.json'];
  const [config, ruleConfig] = await Promise.all(files.map(async file => {
    const response = await fetchFile(new URL('./config/' + file, import.meta.url));
    if (!response.ok) throw new Error('No se ha podido cargar ' + file);
    return response.json();
  }));
  validateClinicalConfig(config, ruleConfig);
  return { config, ruleConfig };
}
function timestamp(date) {
  if (typeof date !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:$|T)/.test(date)) return NaN;
  const day = date.slice(0, 10);
  // Evita aceptar fechas imposibles que Date normaliza (p. ej. 30 de febrero).
  const parsedDay = new Date(day + 'T00:00:00Z');
  if (!Number.isFinite(parsedDay.getTime()) || parsedDay.toISOString().slice(0, 10) !== day) return NaN;
  return Date.parse(date.length === 10 ? day + 'T00:00:00Z' : date);
}
export function getSeries(patient, definition) {
  const field = typeof definition === 'string' ? definition : definition.field;
  const expectedUnit = typeof definition === 'object' ? definition.unit : undefined;
  const records = patient.measurements?.[field];
  if (!Array.isArray(records)) return [];
  const unique = new Map();
  for (const record of records) {
    if (!record || typeof record.value !== 'number' || !Number.isFinite(record.value) ||
        (expectedUnit && record.unit && record.unit !== expectedUnit)) continue;
    const time = timestamp(record.date);
    if (Number.isFinite(time)) unique.set(time, { value: record.value, date: record.date, time });
  }
  return [...unique.values()].sort((a, b) => a.time - b.time);
}
const precise = value => Number(value.toPrecision(12));
export function summarizeIndicator(patient, definition) {
  const series = getSeries(patient, definition);
  const latest = series.at(-1) ?? null, previous = series.at(-2) ?? null;
  return {
    ...definition, series, latest, previous,
    delta: latest && previous ? precise(latest.value - previous.value) : 0,
    percentChange: latest && previous && previous.value !== 0 ? precise((latest.value - previous.value) / Math.abs(previous.value) * 100) : null,
    min: series.length ? Math.min(...series.map(point => point.value)) : null,
    max: series.length ? Math.max(...series.map(point => point.value)) : null
  };
}
export function getIndicatorRows(patient, config) { return config.indicators.map(definition => summarizeIndicator(patient, definition)); }
export function evaluateFindings(patient, config, ruleConfig) {
  const definitions = new Map(config.indicators.map(definition => [definition.field, definition]));
  const summaries = new Map();
  return ruleConfig.rules.flatMap(rule => {
    if (rule.enabled === false) return [];
    const definition = definitions.get(rule.field);
    if (!definition) return [];
    if (!summaries.has(rule.field)) summaries.set(rule.field, summarizeIndicator(patient, definition));
    const summary = summaries.get(rule.field);
    // Un hallazgo de cambio requiere dos mediciones distintas, válidas y comparables.
    if (!summary.previous || !summary.latest) return [];
    const intervalDays = (summary.latest.time - summary.previous.time) / 86400000;
    if (rule.maxIntervalDays !== undefined && intervalDays > rule.maxIntervalDays) return [];
    const values = { current: summary.latest.value, previous: summary.previous.value, delta: summary.delta, percent_change: summary.percentChange };
    const matches = rule.conditions.every(condition => {
      const value = values[condition.metric], compare = operators[condition.operator];
      return Number.isFinite(value) && Object.hasOwn(operators, condition.operator) && compare(value, condition.value);
    });
    return matches ? [{ ...rule, indicator: summary, intervalDays }] : [];
  });
}
// Categorías de eGFR y ACR de la figura 13 de KDIGO 2024.
// No establece diagnóstico de ERC ni confirma persistencia de las alteraciones.
// https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf
export function kdigoCategory(egfr, acr) {
  if (!Number.isFinite(egfr) || !Number.isFinite(acr) || egfr < 0 || acr < 0) return null;
  const g = egfr >= 90 ? 'G1' : egfr >= 60 ? 'G2' : egfr >= 45 ? 'G3a' : egfr >= 30 ? 'G3b' : egfr >= 15 ? 'G4' : 'G5';
  const a = acr < 30 ? 'A1' : acr < 300 ? 'A2' : 'A3';
  return g + ' · ' + a;
}
export function patientKdigo(patient, config) {
  const egfr = config.indicators.find(item => item.field === config.kdigoFields.egfr);
  const acr = config.indicators.find(item => item.field === config.kdigoFields.acr);
  if (!egfr || !acr || egfr.unit !== 'mL/min/1,73 m²' || acr.unit !== 'mg/g') return null;
  return kdigoCategory(getSeries(patient, egfr).at(-1)?.value, getSeries(patient, acr).at(-1)?.value);
}

