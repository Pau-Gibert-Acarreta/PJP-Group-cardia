// Ajuste clínico de la clasificación de riesgo (alto, medio, bajo).
// El médico puede cambiar la clasificación, nunca la probabilidad calculada por el modelo.
//
// HOY: los ajustes se guardan en localStorage.
// MAÑANA (backend): guardarlos con api.setRiskClassification / api.clearRiskClassification (api-client.js),
// para que queden registrados con autor, fecha y motivo.
import { riskLevel, RISK_LEVELS } from '../domain/risk.js';
import { getPatients, findPatient } from './patient-service.js';
import { readStorage, saveStorage, STORAGE_KEYS } from './storage.js';

const CLINICIAN = 'Dra. Carmen Vidal';

const stored = readStorage(STORAGE_KEYS.riskOverrides, {});
const overrides = stored && typeof stored === 'object' && !Array.isArray(stored) ? stored : {};

const isValid = o => o && RISK_LEVELS.includes(o.level) && typeof o.reason === 'string' && typeof o.date === 'string';

// Aplica los ajustes guardados a los pacientes al cargar la app.
getPatients().forEach(p => { if (isValid(overrides[p.id])) p.riskOverride = overrides[p.id]; });

const persist = () => saveStorage(STORAGE_KEYS.riskOverrides, overrides);

// Guarda la clasificación elegida por el médico. Si coincide con la del modelo, elimina el ajuste.
// Devuelve si el cambio se ha podido guardar en el navegador.
export function setRiskClassification(patientId, level, reason) {
  const p = findPatient(patientId);
  if (!p || !RISK_LEVELS.includes(level)) return false;
  if (level === riskLevel(p.risk)) return clearRiskClassification(patientId);
  const override = { level, reason: reason.trim(), author: CLINICIAN, date: new Date().toISOString(), modelLevel: riskLevel(p.risk) };
  p.riskOverride = override; overrides[patientId] = override;
  return persist();
}

// Vuelve a la clasificación del modelo.
export function clearRiskClassification(patientId) {
  const p = findPatient(patientId);
  if (p) delete p.riskOverride;
  delete overrides[patientId];
  return persist();
}
