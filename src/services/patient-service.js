// Acceso a los pacientes. Las vistas solo hablan con este servicio, nunca con los datos directamente.
//
// HOY: pacientes de demostración en memoria + seguimiento guardado en localStorage.
// MAÑANA (backend): sustituir el contenido de estas funciones por llamadas a api-client.js
// (por ejemplo, cargar la lista en loadPatients() y llamar a api.setFollowup en toggleFollowup()).
import { demoPatients } from '../data/demo/patients.js';
import { readStorage, saveStorage, STORAGE_KEYS } from './storage.js';

const patients = demoPatients;

const storedFollowups = readStorage(STORAGE_KEYS.followups, {});
patients.forEach(p => { if (typeof storedFollowups?.[p.id] === 'boolean') p.followup = storedFollowups[p.id]; });

export const getPatients = () => patients;

export const findPatient = id => patients.find(p => p.id === id);

// Marca o desmarca el seguimiento. Devuelve el paciente y si el cambio se ha podido guardar.
export function toggleFollowup(id) {
  const patient = findPatient(id);
  patient.followup = !patient.followup;
  const persisted = saveStorage(STORAGE_KEYS.followups, Object.fromEntries(patients.map(p => [p.id, p.followup])));
  return { patient, persisted };
}
