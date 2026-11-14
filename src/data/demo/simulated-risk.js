// Riesgo cardiovascular SIMULADO para los pacientes que llegan del backend.
//
// El modelo de ML (bloque 4B) todavía no existe, así que la probabilidad, su historial y las
// variables explicativas se inventan aquí de forma determinista (mismo paciente, mismo valor).
// No es un modelo clínico: mezcla la edad con un número pseudoaleatorio derivado del id para que
// el semáforo tenga variedad y no sea absurdo. Cuando exista 4B, esto se sustituye por
// api.getRiskAssessments (risk_prediction en la base de datos).
import { getSeries } from '../../domain/measurements.js';
import { formatNumber } from '../../utils/format.js';

// Número en [0, 1) estable para cada texto (FNV-1a).
export function stableRandom(text) {
  let h = 2166136261;
  for (const c of String(text)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967296;
}

const latest = (p, field) => getSeries(p, field).at(-1)?.value;
const show = (value, decimals, unit) => value === undefined ? 'Sin datos' : formatNumber(value, decimals) + ' ' + unit;

export function simulateRisk(p) {
  const ageFactor = Math.min(1, Math.max(0, ((p.age ?? 50) - 30) / 50));
  const mix = 0.6 * ageFactor + 0.4 * stableRandom(p.id);
  const risk = +(1.5 + 35 * mix ** 1.5).toFixed(1);
  const diabetic = p.conditions.includes('Diabetes tipo 2');
  const factors = [
    { label: 'Presión arterial sistólica', value: show(latest(p, 'systolic'), 0, 'mmHg'), weight: 89 },
    { label: 'Colesterol LDL', value: show(latest(p, 'ldl'), 0, 'mg/dL'), weight: 73 },
    diabetic
      ? { label: 'Diabetes tipo 2', value: show(latest(p, 'hba1c'), 1, '% HbA1c'), weight: 58 }
      : { label: 'Edad', value: p.age + ' años', weight: 58 },
    { label: 'Función renal (FGe)', value: show(latest(p, 'egfr'), 0, 'mL/min/1,73 m²'), weight: 39 },
    { label: 'Albuminuria (CAC)', value: show(latest(p, 'acr'), 0, 'mg/g'), weight: 26 }
  ];
  const history = [risk - 4.8, risk - 3.1, risk - 3.9, risk - 1.2, risk - 1.8, risk].map(v => Math.max(1, +v.toFixed(1)));
  return { risk, factors, history: { risk: history } };
}
