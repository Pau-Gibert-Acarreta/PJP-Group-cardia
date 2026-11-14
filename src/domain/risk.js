// Niveles del semáforo de riesgo cardiovascular (umbrales ilustrativos de la demo).
//
// Hay dos clasificaciones:
// - La del modelo, que se deriva de la probabilidad (p.risk) y no se puede modificar.
// - La final, que es la del modelo salvo que el médico la haya ajustado (p.riskOverride).
//   Es la que se usa para priorizar: listado, filtros, contadores y exportación.

export const RISK_LABELS = { high: 'Alto', medium: 'Medio', low: 'Bajo' };

export const RISK_LEVELS = ['high', 'medium', 'low'];

// Clasificación que corresponde a una probabilidad según el modelo.
export function riskLevel(risk) {
  return risk >= 20 ? 'high' : risk >= 10 ? 'medium' : 'low';
}

// Clasificación final del paciente: la ajustada por el médico o, si no hay ajuste, la del modelo.
export function effectiveRiskLevel(patient) {
  const override = patient.riskOverride?.level;
  return RISK_LEVELS.includes(override) ? override : riskLevel(patient.risk);
}

export const isRiskOverridden = patient => effectiveRiskLevel(patient) !== riskLevel(patient.risk);
