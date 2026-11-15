// Categorías de eGFR y ACR de la figura 13 de KDIGO 2024.
// No establece diagnóstico de ERC ni confirma persistencia de las alteraciones.
// https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf
import { getSeries } from './measurements.js';

export function kdigoCategory(egfr, acr) {
  if (!Number.isFinite(egfr) || !Number.isFinite(acr) || egfr < 0 || acr < 0) return null;
  const g = egfr >= 90 ? 'G1' : egfr >= 60 ? 'G2' : egfr >= 45 ? 'G3a' : egfr >= 30 ? 'G3b' : egfr >= 15 ? 'G4' : 'G5';
  const a = acr < 30 ? 'A1' : acr < 300 ? 'A2' : 'A3';
  return g + ' · ' + a;
}

// Mapa de riesgo KDIGO (filtrado G × albuminuria A): bajo, moderado, alto o muy alto.
const RISK_MAP = {
  G1: ['low', 'moderate', 'high'], G2: ['low', 'moderate', 'high'],
  G3a: ['moderate', 'high', 'very-high'], G3b: ['high', 'very-high', 'very-high'],
  G4: ['very-high', 'very-high', 'very-high'], G5: ['very-high', 'very-high', 'very-high']
};
export const KDIGO_RISK_LABELS = { low: 'bajo', moderate: 'moderadamente aumentado', high: 'alto', 'very-high': 'muy alto' };

export function kdigoRisk(egfr, acr) {
  const category = kdigoCategory(egfr, acr);
  if (!category) return null;
  const [g, a] = category.split(' · ');
  return RISK_MAP[g][Number(a.slice(1)) - 1];
}

function latestKdigoValues(patient, config) {
  const egfr = config.indicators.find(item => item.field === config.kdigoFields.egfr);
  const acr = config.indicators.find(item => item.field === config.kdigoFields.acr);
  if (!egfr || !acr || egfr.unit !== 'mL/min/1,73 m²' || acr.unit !== 'mg/g') return [undefined, undefined];
  return [getSeries(patient, egfr).at(-1)?.value, getSeries(patient, acr).at(-1)?.value];
}

export function patientKdigoRisk(patient, config) {
  return kdigoRisk(...latestKdigoValues(patient, config));
}

export function patientKdigo(patient, config) {
  const egfr = config.indicators.find(item => item.field === config.kdigoFields.egfr);
  const acr = config.indicators.find(item => item.field === config.kdigoFields.acr);
  if (!egfr || !acr || egfr.unit !== 'mL/min/1,73 m²' || acr.unit !== 'mg/g') return null;
  return kdigoCategory(getSeries(patient, egfr).at(-1)?.value, getSeries(patient, acr).at(-1)?.value);
}
