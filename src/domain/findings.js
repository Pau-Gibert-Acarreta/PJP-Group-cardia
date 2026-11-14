// Hallazgos activos: reglas configurables (finding-rules.json) evaluadas sobre las dos últimas mediciones.
import { summarizeIndicator } from './measurements.js';

export const conditionMetrics = new Set(['current', 'previous', 'delta', 'percent_change']);

export const operators = {
  gt: (a, b) => a > b, gte: (a, b) => a >= b,
  lt: (a, b) => a < b, lte: (a, b) => a <= b, eq: (a, b) => a === b
};

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
