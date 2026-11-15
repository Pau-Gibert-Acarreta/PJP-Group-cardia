// Acceso a los pacientes. Las vistas solo hablan con este servicio, nunca con la API directamente.
//
// Datos del Core Backend API (base de datos): identidad, contacto, antecedentes, mediciones,
// línea temporal, notas, seguimiento y la predicción de riesgo del modelo (con su explicación SHAP).
import { api } from './api-client.js';
import { toPatient, mergeDetail } from './patient-adapter.js';

let patients = [];
let byId = new Map();
const detailRequests = new Map();

// Carga el cupo completo. Se llama una vez al arrancar (bootstrap.js).
export async function loadPatients() {
  const { items } = await api.getPatients();
  patients = items.map(toPatient);
  byId = new Map(patients.map(p => [p.id, p]));
  detailRequests.clear();
  return patients;
}

export const getPatients = () => patients;

export const findPatient = id => byId.get(id);

// Completa el paciente con su ficha (contacto, eventos, notas). Una sola petición aunque se pida varias veces.
export function loadPatientDetail(id) {
  const patient = byId.get(id);
  if (!patient) return Promise.resolve(null);
  if (patient.detailLoaded) return Promise.resolve(patient);
  if (!detailRequests.has(id)) {
    detailRequests.set(id, api.getPatient(id)
      .then(detail => mergeDetail(patient, detail))
      .finally(() => detailRequests.delete(id)));
  }
  return detailRequests.get(id);
}

// Marca o desmarca el seguimiento en el servidor. Si falla, se deshace el cambio y se lanza el error.
export async function toggleFollowup(id) {
  const patient = findPatient(id);
  const next = !patient.followup;
  patient.followup = next;
  try {
    await api.setFollowup(id, next);
  } catch (error) {
    patient.followup = !next;
    throw error;
  }
  return patient;
}
