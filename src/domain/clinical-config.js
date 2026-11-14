// Validación de la configuración clínica (indicators.json y finding-rules.json).
import { conditionMetrics, operators } from './findings.js';

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
